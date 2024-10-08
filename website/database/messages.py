"""This files defines the classes for the built-in chat. `Chat`, `Message`, and
`Notification` are stored in the database
"""

from website import db


class Chat(db.Model):
    """Stores chats with 2 or more players"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    messages = db.relationship("Message", backref="chat", lazy="dynamic")


class Message(db.Model):
    """A class for storing data about messages for the in-game messaging system"""

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    time = db.Column(db.DateTime)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"))
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"))

    def package(self):
        """Serializes this message's data into a dictionary"""
        return {
            "id": self.id,
            "text": self.text,
            "date": self.time.timestamp(),
            "player_id": self.player_id,
        }


class Notification(db.Model):
    """A class for storing data about in-game notifications"""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    content = db.Column(db.Text)
    time = db.Column(db.DateTime)
    read = db.Column(db.Boolean, default=False)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"))


# table that links chats to players
player_chats = db.Table(
    "player_chats",
    db.Column("player_id", db.Integer, db.ForeignKey("player.id")),
    db.Column("chat_id", db.Integer, db.ForeignKey("chat.id")),
)
