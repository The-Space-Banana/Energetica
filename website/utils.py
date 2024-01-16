"""
I dumped all small helpful functions here
"""

import requests
import json
import math
import threading
import pickle
import os
import time
import numpy as np
from .database import Player, Network, Resource_on_sale, Shipment, Chat
from . import db
from flask import current_app, flash

flash_error = lambda msg: flash(msg, category="error")

# this function is executed after an asset is finished facility :
def add_asset(player, facility):
    setattr(player, facility, getattr(player, facility) + 1)
    current_app.config["engine"].config.update_config_for_user(player.id)
    print(f"{player.username} has finished the construction of facility {facility}")

# this function is executed when a resource shippment arrives :
def store_import(player, resource, quantity):
    max_cap = current_app.config["engine"].config[player.id][
        "warehouse_capacities"][resource]
    if getattr(player, resource) + quantity > max_cap:
        setattr(player, resource, max_cap)
        # excess ressources are stored in the ground
        setattr(player.tile[0], resource, getattr(player.tile[0], resource) + 
                getattr(player, resource) + quantity - max_cap)
    else :
        setattr(player, resource, getattr(player, resource) + quantity)
    print(f"{player.username} received a shipment of {quantity} kg {resource}")

# format for price display
def display_money(price):
    return f"{price:,.0f}<img src='/static/images/icons/coin.svg' class='coin' alt='coin'>".replace(",", "'")

# checks if a chat with exactly these participants already exists
def check_existing_chats(participants):
    participant_ids = [participant.id for participant in participants]
    conditions = [Chat.participants.any(id=participant_id) for participant_id in participant_ids]
    existing_chats = Chat.query.filter(*conditions)
    for chat in existing_chats:
        if len(chat.participants)==len(participants):
            return True
    return False

# This function upddates the windspeed and irradiation data every 10 mminutes by using the meteosuisse api
def update_weather(engine):
    url_wind = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-windgeschwindigkeit-kmh-10min/ch.meteoschweiz.messwerte-windgeschwindigkeit-kmh-10min_en.json"
    url_irr = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-globalstrahlung-10min/ch.meteoschweiz.messwerte-globalstrahlung-10min_en.json"
    t = engine.data["current_t"]
    try:
        response = requests.get(url_wind)
        if response.status_code == 200:
            windspeed = json.loads(response.content)['features'][107]['properties']['value']
            interpolation = np.linspace(engine.data["current_windspeed"][t-1], windspeed, 11)
            engine.data["current_windspeed"][t : t+10] = interpolation[1:]
        else:
            print("Failed to fetch the file. Status code:", response.status_code)
            engine.data["current_windspeed"][t : t+10] = [engine.data["current_windspeed"][t-1]]*10
    except Exception as e:
        print("An error occurred:", e)
        engine.data["current_windspeed"][t : t+10] = [engine.data["current_windspeed"][t-1]]*10

    try:
        response = requests.get(url_irr)
        if response.status_code == 200:
            irradiation = json.loads(response.content)['features'][65]['properties']['value']
            interpolation = np.linspace(engine.data["current_irradiation"][t-1], irradiation, 11)
            engine.data["current_irradiation"][t : t+10] = interpolation[1:]
        else:
            print("Failed to fetch the file. Status code:", response.status_code)
            engine.data["current_irradiation"][t : t+10] = [engine.data["current_irradiation"][t-1]]*10
    except Exception as e:
        print("An error occurred:", e)
        engine.data["current_irradiation"][t : t+10] = [engine.data["current_irradiation"][t-1]]*10

    month = math.floor((engine.data["total_t"]%73440)/6120) # One year in game is 51 days
    f = (engine.data["total_t"]%73440)/6120 - month
    d = engine.river_discharge
    power_factor = d[month]+(d[(month+1)%12]-d[month])*f
    engine.data["current_discharge"][t : t+10] = [power_factor]*10
    print(f"the current irradiation in Zürich is {engine.data['current_irradiation'][t+9]} W/m2 with a windspeed of {engine.data['current_windspeed'][t+9]} km/h")

# saves the past production data to files every 24h AND remove network data older than 24h
def save_past_data_threaded(app, engine, new_data, network_data):
    def save_data():
        with app.app_context():
            players = Player.query.all()
            for player in players:
                past_data = {}
                for timescale in ["5_days", "month", "6_months"]:
                    with open(f"instance/player_data/{player.username}/{timescale}.pck", "rb") as file:
                        past_data[timescale] = pickle.load(file)
                
                past_data["day"] = new_data[player.username]
                for category in past_data["5_days"]:
                    for element in past_data["5_days"][category]:
                        new_array = np.array(new_data[player.username][category][element])
                        new_5_days = np.mean(new_array.reshape(-1, 5), axis=1)
                        past_data["5_days"][category][element] = past_data["5_days"][category][element][288:]
                        past_data["5_days"][category][element].extend(new_5_days)
                        new_month = np.mean(new_5_days.reshape(-1, 6), axis=1)
                        past_data["month"][category][element] = past_data["month"][category][element][48:]
                        past_data["month"][category][element].extend(new_month)
                        new_6_months = np.mean(new_month.reshape(-1, 6), axis=1)
                        past_data["6_months"][category][element] = past_data["6_months"][category][element][8:]
                        past_data["6_months"][category][element].extend(new_6_months)

                for timescale in past_data:
                    with open(f"instance/player_data/{player.username}/{timescale}.pck", "wb") as file:
                        pickle.dump(past_data[timescale], file)

            # remove old network files AND save past prices
            networks = Network.query.all()
            for network in networks:
                network_dir = f"instance/network_data/{network.name}/charts/"
                files = os.listdir(network_dir)
                for filename in files:
                    t_value = int(filename.split("market_t")[1].split(".pck")[0])
                    if t_value < engine.data['total_t']-1440:
                        os.remove(os.path.join(network_dir, filename))

                past_data = {}
                for timescale in ["5_days", "month", "6_months"]:
                    with open(f"instance/network_data/{network.name}/prices/{timescale}.pck", "rb") as file:
                        past_data[timescale] = pickle.load(file)
                
                past_data["day"] = network_data[network.name]
                for element in past_data["5_days"]:
                    new_array = np.array(network_data[network.name][element])
                    new_5_days = np.mean(new_array.reshape(-1, 5), axis=1)
                    past_data["5_days"][element] = past_data["5_days"][element][288:]
                    past_data["5_days"][element].extend(new_5_days)
                    new_month = np.mean(new_5_days.reshape(-1, 6), axis=1)
                    past_data["month"][element] = past_data["month"][element][48:]
                    past_data["month"][element].extend(new_month)
                    new_6_months = np.mean(new_month.reshape(-1, 6), axis=1)
                    past_data["6_months"][element] = past_data["6_months"][element][8:]
                    past_data["6_months"][element].extend(new_6_months)

                for timescale in past_data:
                    with open(f"instance/network_data/{network.name}/prices/{timescale}.pck", "wb") as file:
                        pickle.dump(past_data[timescale], file)

            print("past 24h data has been saved to files")

    thread = threading.Thread(target=save_data)
    thread.start()

def data_init_network(length):
    return {
        "price": [0] * length,
        "quantity": [0] * length,
        }

def put_resource_on_market(player, resource, quantity, price):
    """Put an offer on the resource market"""
    if getattr(player, resource)-getattr(player, resource+"_on_sale") < quantity:
        flash_error(f"You have not enough {resource} available")
    else:
        setattr(player, resource+"_on_sale", getattr(player, resource+"_on_sale")+quantity)
        new_sale = Resource_on_sale(resource=resource, 
                                    quantity=quantity, 
                                    price=price, 
                                    player=player)
        db.session.add(new_sale)
        db.session.commit()  
        flash(f"You put {quantity/1000}t of {resource} on sale for {price*1000}<img src='/static/images/icons/coin.svg' class='coin' alt='coin'>/t", category="message")

def buy_resource_from_market(player, quantity, sale_id):
    """Buy an offer from the resource market"""
    sale = Resource_on_sale.query.filter_by(id=sale_id).first()
    if player == sale.player:
        # Player is buying their own resource
        if quantity == sale.quantity:
            Resource_on_sale.query.filter_by(id=sale_id).delete()
        else :
            sale.quantity -= quantity
        setattr(player, sale.resource+"_on_sale", getattr(player, sale.resource+"_on_sale")-quantity)
        db.session.commit()
        flash(f"You removed {quantity/1000}t of {sale.resource} from the market", category="message")
    elif sale.price * quantity > player.money:
        flash_error(f"You have not enough money")
    else:
        # Player can purchased from different player
        if quantity == sale.quantity:
            # Player is purchasing all available quantity
            Resource_on_sale.query.filter_by(id=sale_id).delete()
        else :
            # Some resources remain after transaction
            sale.quantity -= quantity
        player.money -= sale.price * quantity
        sale.player.money += sale.price * quantity
        player.update_resources()
        sale.player.update_resources()
        setattr(sale.player, sale.resource, getattr(sale.player, sale.resource) - quantity)
        setattr(sale.player, sale.resource+"_on_sale", getattr(sale.player, sale.resource+"_on_sale") - quantity)
        dq = player.tile[0].q - sale.player.tile[0].q
        dr = player.tile[0].r - sale.player.tile[0].r
        distance = math.sqrt(2 * (dq**2 + dr**2 + dq*dr))
        shipment_duration = distance * current_app.config["engine"].config["transport"]["time"]
        new_shipment = Shipment(
            resource = sale.resource,
            quantity = quantity,
            departure_time = time.time(),
            duration = shipment_duration,
            player_id = player.id
        )
        db.session.add(new_shipment)
        db.session.commit()