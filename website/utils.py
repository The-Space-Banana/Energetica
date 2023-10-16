"""
I dumped all small helpful functions here
"""

import time
from .database import Player, Under_construction, Shipment, Chat
from . import db
from flask import current_app
from sqlalchemy import func

# this function is executed after an asset is finished facility :
def add_asset(player_id, facility):
    player = Player.query.get(int(player_id))
    assets = current_app.config["engine"].config[player_id]["assets"]
    setattr(player, facility, getattr(player, facility) + 1)
    facility_data = assets[facility]
    # player.emissions += ??? IMPLEMENT EMMISIONS FROM CONSTRUCTION
    Under_construction.query.filter(
        Under_construction.finish_time < time.time()
    ).delete()
    db.session.commit()

# this function is executed when a resource shippment arrives :
def store_import(player_id, resource, quantity):
    player = Player.query.get(int(player_id))
    max_cap = current_app.config["engine"].config[player_id][
        "warehouse_capacities"][resource]
    if getattr(player, resource) + quantity > max_cap:
        setattr(player, resource, max_cap)
        # excess ressources are stored in the ground
        setattr(player.tile[0], resource, getattr(player.tile[0], resource) + 
                getattr(player, resource) + quantity - max_cap)
    else :
        setattr(player, resource, getattr(player, resource) + quantity)
    Shipment.query.filter(Shipment.arrival_time < time.time()).delete()
    db.session.commit()

# format for price display
def display_CHF(price):
    return f"{price:,.0f} CHF".replace(",", " ")

# checks if a chat with exactly these participants already exists
def check_existing_chats(participants):
    # Get the IDs of the participants
    participant_ids = [participant.id for participant in participants]

    # Generate the conditions for participants' IDs and count
    conditions = [Chat.participants.any(id=participant_id) for participant_id in participant_ids]

    # Query the Chat table
    existing_chats = Chat.query.filter(*conditions)
    for chat in existing_chats:
        if len(chat.participants)==len(participants):
            return True
    return False