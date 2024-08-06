"""This code is run once at the start of the game"""

import eventlet

eventlet.monkey_patch(thread=True, time=True)

# pylint: disable=wrong-import-order,wrong-import-position
# ruff: noqa: E402

import atexit
import base64
import cProfile
import csv
import os
import pickle
import platform
import pstats
import secrets
import shutil
import socket
from pathlib import Path

from ecdsa import NIST256p, SigningKey
from flask import Flask, jsonify, request, send_file
from flask_apscheduler import APScheduler
from flask_httpauth import HTTPBasicAuth
from flask_login import LoginManager, current_user
from flask_sock import Sock
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash

db = SQLAlchemy()

import website.game_engine

from .database.player import Player


def get_or_create_flask_secret_key() -> str:
    """SECRET_KEY for Flask. Loads it from disk if it exists, creates one and stores it otherwise"""
    filepath = "flask_secret_key.txt"
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        secret_key = secrets.token_hex()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(secret_key)
        return secret_key


def get_or_create_vapid_keys() -> type[str, str]:
    """
    Public private key pair for vapid push notifications. Loads these from disk if they exists, creates a new pair and
    stores it otherwise
    """
    public_key_filepath = "vapid_public_key.txt"
    private_key_filepath = "vapid_private_key.txt"
    if os.path.exists(public_key_filepath) and os.path.exists(private_key_filepath):
        with open(public_key_filepath, "r", encoding="utf-8") as f:
            public_key = f.read().strip()
        with open(private_key_filepath, "r", encoding="utf-8") as f:
            private_key = f.read().strip()
        return public_key, private_key
    else:
        # Generate a new ECDSA key pair
        private_key_obj = SigningKey.generate(curve=NIST256p)
        public_key_obj = private_key_obj.get_verifying_key()

        # Encode the keys using URL- and filename-safe base64 without padding
        private_key = base64.urlsafe_b64encode(private_key_obj.to_string()).rstrip(b"=").decode("utf-8")
        public_key = base64.urlsafe_b64encode(b"\x04" + public_key_obj.to_string()).rstrip(b"=").decode("utf-8")

        # Write the keys to their respective files
        with open(public_key_filepath, "w", encoding="utf-8") as f:
            f.write(public_key)
        with open(private_key_filepath, "w", encoding="utf-8") as f:
            f.write(private_key)

        return public_key, private_key


def create_app(clock_time, in_game_seconds_per_tick, run_init_test_players, rm_instance, random_seed):
    """This function sets up the app and the game engine"""
    # gets lock to avoid multiple instances
    if platform.system() == "Linux":
        lock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        lock.bind("\0energetica")

    # creates the app :
    app = Flask(__name__)
    app.config["SECRET_KEY"] = get_or_create_flask_secret_key()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    (app.config["VAPID_PUBLIC_KEY"], app.config["VAPID_PRIVATE_KEY"]) = get_or_create_vapid_keys()
    app.config["VAPID_CLAIMS"] = {"sub": "mailto:felixvonsamson@gmail.com"}
    db.init_app(app)

    # creates the engine (and loading the save if it exists)
    engine = website.game_engine.GameEngine(clock_time, in_game_seconds_per_tick, random_seed)

    if rm_instance:
        engine.log("removing instance")
        shutil.rmtree("instance")

    from .utils.game_engine import data_init_climate

    Path("instance/player_data").mkdir(parents=True, exist_ok=True)
    if not os.path.isfile("instance/server_data/climate_data.pck"):
        Path("instance/server_data").mkdir(parents=True, exist_ok=True)
        with open("instance/server_data/climate_data.pck", "wb") as file:
            climate_data = data_init_climate(
                in_game_seconds_per_tick, engine.data["random_seed"], engine.data["delta_t"]
            )
            pickle.dump(climate_data, file)

    if os.path.isfile("instance/engine_data.pck"):
        with open("instance/engine_data.pck", "rb") as file:
            engine.data = pickle.load(file)
            engine.log("Loaded engine data from disk.")
    app.config["engine"] = engine

    # initialize socketio :
    socketio = SocketIO(app, cors_allowed_origins="*")  # engineio_logger=True
    engine.socketio = socketio
    from .api.socketio_handlers import add_handlers

    add_handlers(socketio=socketio, engine=engine)

    # initialize sock for WebSockets:
    sock = Sock(app)
    engine.sock = sock
    from .api.websocket import add_sock_handlers

    add_sock_handlers(sock=sock, engine=engine)

    # add blueprints (website repositories) :
    from .api.http import http
    from .api.websocket import websocket_blueprint
    from .auth import auth
    from .views import overviews, views

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(overviews, url_prefix="/production_overview")
    app.register_blueprint(auth, url_prefix="/")
    app.register_blueprint(http, url_prefix="/api/")
    app.register_blueprint(websocket_blueprint, url_prefix="/api/")

    @app.route("/subscribe", methods=["GET", "POST"])
    def subscribe():
        """
        POST creates a new subscription
        GET returns vapid public key
        """
        if request.method == "GET":
            return jsonify({"public_key": app.config["VAPID_PUBLIC_KEY"]})
        subscription = request.json
        if "endpoint" not in subscription:
            return jsonify({"response": "Invalid subscription"})
        engine.notification_subscriptions[current_user.id].append(subscription)
        return jsonify({"response": "Subscription successful"})

    @app.route("/unsubscribe", methods=["POST"])
    def unsubscribe():
        """
        POST removes a subscription
        """
        subscription = request.json
        if subscription in engine.notification_subscriptions[current_user.id]:
            engine.notification_subscriptions[current_user.id].remove(subscription)
        return jsonify({"response": "Unsubscription successful"})

    @app.route("/apple-app-site-association")
    def apple_app_site_association():
        """
        Returns the apple-app-site-association JSON data needed for supporting
        associated domains needed for shared webcredentials
        """
        return send_file("static/apple-app-site-association", as_attachment=True)

    from .database.map import Hex

    # initialize database :
    with app.app_context():
        db.create_all()
        # if map data not already stored in database, read map.csv and store it in database
        if Hex.query.count() == 0:
            with open("website/static/data/map.csv", "r") as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    hex = Hex(
                        q=row["q"],
                        r=row["r"],
                        solar=float(row["solar"]),
                        wind=float(row["wind"]),
                        hydro=float(row["hydro"]),
                        coal=float(row["coal"]),
                        oil=float(row["oil"]),
                        gas=float(row["gas"]),
                        uranium=float(row["uranium"]),
                    )
                    db.session.add(hex)
                db.session.commit()

    # initialize login manager
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        player = Player.query.get(int(id))
        return player

    # initialize HTTP basic auth
    engine.auth = HTTPBasicAuth()

    @engine.auth.verify_password
    def verify_password(username, password):
        player = Player.query.filter_by(username=username).first()
        if player:
            if check_password_hash(player.pwhash, password):
                return player

    # initialize the schedulers and add the recurrent functions :
    # This function is to run the following only once, TO REMOVE IF DEBUG MODE IS SET TO FALSE
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        from .utils.game_engine import state_update

        scheduler = APScheduler()
        scheduler.init_app(app)

        scheduler.add_job(
            func=state_update,
            args=(engine, app),
            id="state_update",
            trigger="cron",
            second=f"*/{clock_time}" if clock_time != 60 else "0",
            misfire_grace_time=10,
        )
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown())

        if run_init_test_players:
            engine.log("running init_test_players")
            with app.app_context():
                # Temporary automated player creation for testing
                from .init_test_players import init_test_players

                init_test_players(engine)

                # # Profiling
                # profiler = cProfile.Profile()
                # profiler.runctx("state_update(engine, app)", globals(), locals())
                # profiler.dump_stats("restats")
                # p = pstats.Stats("restats")
                # p.sort_stats("cumulative").print_stats(20)
    return socketio, sock, app
