"""
In this file, the main routes of the website are managed
"""

from flask import Blueprint, render_template, request, flash, jsonify, session
from flask import g, current_app
from flask_login import login_required, current_user
import pickle
import datetime
import math
import time
import heapq
from . import db
from . import heap
from .database import Chat, Player, Network, Resource_on_sale, Shipment
from .utils import check_existing_chats, display_CHF, store_import

views = Blueprint("views", __name__)

flash_error = lambda msg: flash(msg, category="error")

# this function is executed once before every request :
@views.before_request
@login_required
def check_user():
    g.engine = current_app.config["engine"]
    if len(current_user.tile) == 0:
        return render_template(
                "location_choice.jinja",
                engine=g.engine,
                user=current_user
            )
    
    g.config = g.engine.config[current_user.id]

    def render_template_ctx(page):
        # render template with or without player production data
        if page == "messages.jinja":
            chats=Chat.query.filter(Chat.participants.any(id=current_user.id)).all()
            return render_template(
                page,
                engine=g.engine,
                user=current_user,
                chats=chats
            )
        elif page == "resource_market.jinja":
            on_sale=Resource_on_sale.query.all()
            return render_template(
                page,
                engine=g.engine,
                user=current_user,
                on_sale=on_sale,
                data=g.config
            )
        else:
            return render_template(
                page,
                engine=g.engine,
                user=current_user,
                data=g.config["assets"]
            )

    g.render_template_ctx = render_template_ctx

@views.route("/", methods=["GET", "POST"])
@views.route("/home", methods=["GET", "POST"])
def home():
    return g.render_template_ctx("home.jinja")

@views.route("/messages", methods=["GET", "POST"])
def messages():
    if request.method == "POST":
        # If player is trying to create a chat with one other player
        if "add_chat_username" in request.form:
            buddy_username = request.form.get("add_chat_username")
            if buddy_username == current_user.username:
                flash_error("Cannot create a chat with yourself")
                return g.render_template_ctx("messages.jinja")
            buddy = Player.query.filter_by(username=buddy_username).first()
            if buddy is None:
                flash_error("No Player with this username")
                return g.render_template_ctx("messages.jinja")
            if check_existing_chats([current_user, buddy]):
                flash_error("Chat already exists")
                return g.render_template_ctx("messages.jinja")
            new_chat = Chat(
                name=current_user.username+buddy_username,
                participants=[current_user, buddy]
                )
            db.session.add(new_chat)
            db.session.commit()
        else:
            current_user.show_disclamer = False
            if request.form.get("dont_show_disclaimer") == "on":
                db.session.commit()
    return g.render_template_ctx("messages.jinja")

@views.route("/network", methods=["GET", "POST"])
def network():
    if request.method == "POST":
        # If player is trying to join a network
        network_name = request.form.get("choose_network")
        if len(network_name) < 3 or len(network_name) > 50:
            flash_error("Network name has to have at least 3 characters and no more than 50")
        else :
            network = Network.query.filter_by(name=network_name).first()
            current_user.network = network
            db.session.commit()  
            flash(f"You joined the network {network_name}", category="message")  
    return g.render_template_ctx("network.jinja")

@views.route("/power_facilities")
def energy_facilities():
    return g.render_template_ctx("power_facilities.jinja")

@views.route("/storage_facilities")
def storage_facilities():
    return g.render_template_ctx("storage_facilities.jinja")

@views.route("/technology")
def technology():
    return g.render_template_ctx("technologies.jinja")

@views.route("/functional_facilities")
def functional_facilities():
    return g.render_template_ctx("functional_facilities.jinja")

@views.route("/extraction_plants")
def extraction_plants():
    return g.render_template_ctx("extraction_plants.jinja")

@views.route("/production_overview")
def production_overview():
    return g.render_template_ctx("production_overview.jinja")

@views.route("/resource_market", methods=["GET", "POST"])
def resource_market():
    if request.method == "POST":
        # If player is trying to put resources on sale
        if "resource" in request.form:
            resource = request.form.get("resource")
            quantity = float(request.form.get("quantity"))*1000
            price = float(request.form.get("price"))/1000
            if getattr(current_user, resource)-getattr(current_user, resource+"_on_sale") < quantity:
                flash_error(f"You have not enough {resource} avalable")
            else:
                setattr(current_user, resource+"_on_sale", getattr(current_user, resource+"_on_sale")+quantity)
                new_sale = Resource_on_sale(resource=resource, 
                                            quantity=quantity, 
                                            price=price, 
                                            player=current_user)
                db.session.add(new_sale)
                db.session.commit()  
                flash(f"You put {quantity/1000}t of {resource} on sale for {price*1000}CHF/t", category="message")
        else :
            quantity = float(request.form.get("purchases_quantity"))*1000
            sale_id = int(request.form.get("sale_id"))
            sale = Resource_on_sale.query.filter_by(id=sale_id).first()
            if current_user == sale.player:
                if quantity == sale.quantity:
                    Resource_on_sale.query.filter_by(id=sale_id).delete()
                else :
                    sale.quantity -= quantity
                setattr(current_user, sale.resource+"_on_sale", getattr(current_user, sale.resource+"_on_sale")-quantity)
                db.session.commit()
                flash(f"You removed {quantity/1000}t of {sale.resource} from the market", category="message")
            elif sale.price * quantity > current_user.money:
                flash_error(f"You have not enough money")
            else:
                if quantity == sale.quantity:
                    Resource_on_sale.query.filter_by(id=sale_id).delete()
                else :
                    sale.quantity -= quantity
                current_user.money -= sale.price * quantity
                updates = [("money", display_CHF(current_user.money))]
                g.engine.update_fields(updates, [current_user]) # can probably be improved
                sale.player.money += sale.price * quantity
                setattr(sale.player, sale.resource, getattr(sale.player, sale.resource) - quantity)
                setattr(sale.player, sale.resource+"_on_sale", getattr(sale.player, sale.resource+"_on_sale") - quantity)
                dq = current_user.tile[0].q - sale.player.tile[0].q
                dr = current_user.tile[0].r - sale.player.tile[0].r
                distance = math.sqrt(2 * (dq**2 + dr**2 + dq*dr))
                shipment_duration = distance * g.config["transport_speed"]
                arrival_time = time.time() + shipment_duration
                heapq.heappush(heap, (arrival_time, store_import, (current_user.id, sale.resource, quantity)))
                new_shipment = Shipment(
                    resource = sale.resource,
                    quantity = quantity,
                    departure_time = time.time(),
                    arrival_time = arrival_time,
                    player_id = current_user.id
                )
                db.session.add(new_shipment)
                db.session.commit()

    return g.render_template_ctx("resource_market.jinja")