#!/bin/env python3

from website.create_app import create_app

socketio, app = create_app()

if __name__ == "__main__":
  socketio.run(app, debug=True, log_output=False, host="0.0.0.0", port=5001)
