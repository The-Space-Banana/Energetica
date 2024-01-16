"""
These functions make the link between the website and the database
"""

from flask import Blueprint, request, flash, jsonify, g, current_app, redirect
from flask_login import login_required, current_user
import pickle
from pathlib import Path
import numpy as np
from .utils import put_resource_on_market, buy_resource_from_market, data_init_network
from . import db
from .database import Network

api = Blueprint('api', __name__)

from .database import Hex, Player, Chat, Network, Under_construction

@api.before_request
@login_required
def check_user():
    g.engine = current_app.config["engine"]

# gets the map data from the database and returns it as a array of dictionaries :
@api.route("/get_map", methods=["GET"])
def get_map():
    hex_map = Hex.query.all()
    hex_list = [
        {
            "id": tile.id,
            "q": tile.q,
            "r": tile.r,
            "solar": tile.solar,
            "wind": tile.wind,
            "hydro": tile.hydro,
            "coal": tile.coal,
            "oil": tile.oil,
            "gas": tile.gas,
            "uranium": tile.uranium,
            "player": tile.player.username if tile.player else None,
        }
        for tile in hex_map
    ]
    with_id = request.args.get('with_id')
    if with_id is None:
        return jsonify(hex_list)
    else :
        return jsonify(hex_list, current_user.tile[0].id)

# gets all the player usernames (except it's own) and returns it as a list :
@api.route("/get_usernames", methods=["GET"])
def get_usernames():
    username_list = Player.query.with_entities(Player.username).all()
    username_list = [username[0] for username in username_list 
    if username[0]!=current_user.username]
    return jsonify(username_list)

# gets all the network names and returns it as a list :
@api.route("/get_networks", methods=["GET"])
def get_networks():
    network_list = Network.query.with_entities(Network.name).all()
    network_list = [name[0] for name in network_list]
    return jsonify(network_list)

# gets the last 20 messages from a chat and returns it as a list :
@api.route("/get_chat", methods=["GET"])
def get_chat():
    chat_id = request.args.get('chatID')
    messages = Chat.query.filter_by(id=chat_id).first().messages
    messages_list = [(msg.player.username, msg.text) for msg in messages]
    return jsonify(messages_list)

# Gets the data for the overview charts
@api.route("/get_chart_data", methods=["GET"])
def get_chart_data():
    assets = g.engine.config[current_user.id]["assets"]
    timescale = request.args.get('timescale')
    # values for `timescale` are in ["6h", "day", "5_days", "month", "6_months"]
    table = request.args.get('table')
    # values for `table` are in ["demand", "emissions", "generation", "ressources", "revenues", "storage"]
    filename = f"instance/player_data/{current_user.username}/{timescale}.pck"
    with open(filename, "rb") as file:
        data = pickle.load(file)
    if table == "generation" or table == "storage" or table == "ressources":
        capacities = {}
        if table == "generation":
            for facility in ["watermill", "small_water_dam", "large_water_dam", 
                            "nuclear_reactor", "nuclear_reactor_gen4",  
                            "steam_engine", "coal_burner", "oil_burner", 
                            "gas_burner", "combined_cycle", "windmill", 
                            "onshore_wind_turbine", "offshore_wind_turbine", "CSP_solar",
                            "PV_solar"]:
                capacities[facility] = (getattr(current_user, facility) * 
                        assets[facility]["power generation"])
        elif table == "storage":
            for facility in ["small_pumped_hydro", "large_pumped_hydro", 
                             "lithium_ion_batteries", "solid_state_batteries", 
                             "compressed_air", "molten_salt", 
                             "hydrogen_storage"]:
                capacities[facility] = (getattr(current_user, facility) * 
                        assets[facility]["storage capacity"])
        else:
            rates = {}
            on_sale = {}
            resource_to_facility = {
                "coal" : "coal_mine",
                "oil" : "oil_field",
                "gas" : "gas_drilling_site",
                "uranium" : "uranium_mine"
            }
            for ressource in ["coal", "oil", "gas", "uranium"]:
                capacities[ressource] = g.engine.config[current_user.id][
                    "warehouse_capacities"][ressource]
                facility = resource_to_facility[ressource]
                rates[ressource] = getattr(current_user, facility) * assets[
                    facility]["amount produced"] * 60
                on_sale[ressource] = getattr(current_user, ressource+"_on_sale")
            return jsonify(g.engine.data["current_t"], data[table],
                       g.engine.data["current_data"][current_user.username][table],
                       capacities, rates, on_sale)
        return jsonify(g.engine.data["current_t"], data[table],
                       g.engine.data["current_data"][current_user.username][table],
                       capacities)
    else:
        return jsonify(g.engine.data["current_t"], data[table],
                       g.engine.data["current_data"][current_user.username][table])
    
# Gets the data from the market for the market graph 
@api.route("/get_market_data", methods=["GET"])
def get_market_data():
    market_data = {}
    if current_user.network == None:
        return '', 404
    t = int(request.args.get('t'))
    filename_state = f"instance/network_data/{current_user.network.name}/charts/market_t{g.engine.data['total_t']-t}.pck"
    if Path(filename_state).is_file():
        with open(filename_state, "rb") as file:
            market_data = pickle.load(file)
            market_data["capacities"] = market_data["capacities"].to_dict(orient='list')
            market_data["capacities"]["player"] = [player.username for player in market_data["capacities"]["player"]]
            market_data["demands"] = market_data["demands"].to_dict(orient='list')
            market_data["demands"]["player"] = [player.username for player in market_data["demands"]["player"]]
            market_data["demands"]["price"] = [None if price == np.inf else price for price in market_data["demands"]["price"]]
    else:
        market_data = None
    timescale = request.args.get('timescale')
    filename_prices = f"instance/network_data/{current_user.network.name}/prices/{timescale}.pck"
    with open(filename_prices, "rb") as file:
        prices = pickle.load(file)
    return jsonify(g.engine.data["current_t"], market_data, prices, g.engine.data["network_data"][current_user.network.name])

# Gets list of facilities under construction and config informations to calculate the values to display
@api.route("/get_ud_and_config", methods=["GET"])
def get_ud_and_config():
    family = request.args.get('filter')
    constructions = Under_construction.query.filter(
            Under_construction.player_id == current_user.id).filter(
            Under_construction.family == family)
    assets = g.engine.config[current_user.id]["assets"]
    ud = {}
    for construction in constructions:
        if construction.name in ud :
            ud[construction.name]["lvl_future"] += 1
        else :
            lvl = getattr(current_user, construction.name)
            ud[construction.name] = {
                "name": assets[construction.name]["name"],
                "lvl_at": lvl,
                "lvl_future": lvl+1
            }
    player_lvls = current_user.get_technology_values()
    return jsonify(ud, assets, player_lvls)

# Gets list of facilities under construction for this player
@api.route("/get_constructions", methods=["GET"])
def get_constructions():
    constructions = Under_construction.query.filter(
            Under_construction.player_id == current_user.id)
    return jsonify(constructions)

# gets scoreboard data :
@api.route("/get_scoreboard", methods=["GET"])
def get_scoreboard():
    scoreboard_data = []
    players = Player.query.all()
    for player in players:
        scoreboard_data.append([player.username, player.money, player.average_revenues, player.emissions])
    return jsonify(scoreboard_data)

@api.route("/put_resource_on_sale", methods=["POST"])
def put_resource_on_sale():
    """Parse the HTTP form for selling resources"""
    resource = request.form.get("resource")
    quantity = float(request.form.get("quantity"))*1000
    price = float(request.form.get("price"))/1000
    put_resource_on_market(current_user, resource, quantity, price)
    return redirect("/resource_market", code=303)

@api.route("/buy_resource", methods=["POST"])
def buy_resource():
    """Parse the HTTP form for buying resources"""
    quantity = float(request.form.get("purchases_quantity"))*1000
    sale_id = int(request.form.get("sale_id"))
    buy_resource_from_market(current_user, quantity, sale_id)
    return redirect("/resource_market", code=303)

@api.route("join_network", methods=["POST"])
def join_network():
    """player is trying to join a network"""
    network_name = request.form.get("choose_network")
    network = Network.query.filter_by(name=network_name).first()
    current_user.network = network
    db.session.commit()  
    flash(f"You joined the network {network_name}", category="message")
    print(f"{current_user.username} joined the network {current_user.network.name}")
    return redirect("/network", code=303)

@api.route("create_network", methods=["POST"])
def create_network():
    """This endpoint is used when a player creates a network"""
    network_name = request.form.get("network_name")
    if len(network_name) < 3 or len(network_name) > 40:
        print("Network name must be between 3 and 40 characters")
        flash("Network name must be between 3 and 40 characters", category="error")
        return redirect("/network", code=303)
    if Network.query.filter_by(name=network_name).first() is not None:
        print("Network with this name already exists")
        flash("Network with this name already exists", category="error")
        return redirect("/network", code=303)
    new_Network = Network(name=network_name, members=[current_user])
    db.session.add(new_Network)
    db.session.commit()
    Path(f"instance/network_data/{network_name}/charts").mkdir(
        parents=True, exist_ok=True
    )
    g.engine.data["network_data"][network_name] = data_init_network(1441)
    past_data = data_init_network(1440)
    Path(f"instance/network_data/{network_name}/prices").mkdir(
        parents=True, exist_ok=True
    )
    for timescale in ["day", "5_days", "month", "6_months"]:
        with open(
            f"instance/network_data/{network_name}/prices/{timescale}.pck", "wb"
        ) as file:
            pickle.dump(past_data, file)
    print(f"{current_user.username} created the network {network_name}")
    return redirect("/network", code=303)