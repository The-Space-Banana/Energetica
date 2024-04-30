from website import db


class Chat(db.Model):
    """Stores chats with 2 or more players"""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    messages = db.relationship("Message", backref="chat", lazy="dynamic")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    time = db.Column(db.DateTime)
    player_id = db.Column(db.Integer, db.ForeignKey("player.id"))
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"))


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    content = db.Column(db.Text)
    time = db.Column(db.DateTime)
    read = db.Column(db.Boolean, default=False)


# table that links chats to players
player_chats = db.Table(
    "player_chats",
    db.Column("player_id", db.Integer, db.ForeignKey("player.id")),
    db.Column("chat_id", db.Integer, db.ForeignKey("chat.id")),
)
# table that links notifications to players
player_notifications = db.Table(
    "player_notifications",
    db.Column("player_id", db.Integer, db.ForeignKey("player.id")),
    db.Column("notification_id", db.Integer, db.ForeignKey("notification.id")),
)
