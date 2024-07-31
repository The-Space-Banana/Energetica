#!/usr/bin/env python3

"""This code launches the game"""
# TODO: regenerate a new public/private key pair and stop tracking it it git

import argparse

from website import create_app

parser = argparse.ArgumentParser()
parser.add_argument(
    "--clock_time",
    type=int,
    choices=[60, 30, 20, 15, 12, 10, 6, 5, 4, 3, 2, 1],
    default=60,
    help="Set the clock time interval in seconds (default: 60)",
)
parser.add_argument(
    "--in_game_seconds_per_tick",
    type=int,
    choices=[3600, 1800, 1200, 900, 600, 540, 480, 420, 360, 300, 240, 180, 120, 60, 30],
    default=240,
    help="Set  how many in-game seconds are in a tick (default: 240)",
)
parser.add_argument(
    "--run_init_test_players",
    help="Run the init_test_players function",
    action="store_true",
)
parser.add_argument(
    "--rm_instance",
    help="remove the instance folder",
    action="store_true",
)

args = parser.parse_args()

socketio, sock, app = create_app(
    clock_time=args.clock_time,
    in_game_seconds_per_tick=args.in_game_seconds_per_tick,
    run_init_test_players=args.run_init_test_players,
    rm_instance=args.rm_instance,
)

if __name__ == "__main__":
    socketio.run(app, debug=True, log_output=False, host="0.0.0.0", port=5001)
