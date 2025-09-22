import websocket
import threading
import signal
import time
import json
import re
import pandas as pd

pd.set_option('display.float_format', '{:.8f}'.format)


class WebSocketClient:
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        symbols: list,
        store_data: bool = False,
        display_stream: bool = False,
        display_candle_1m: bool = False,
        display_candle_5m: bool = False,
        display_candle_1h: bool = False,
    ) -> None:
        # Validate API key
        prog = re.compile(r"^[A-z0-9.]{16,32}$")
        if not prog.match(api_key):
            raise ValueError("API key is invalid")

        # Validate endpoint
        if endpoint not in ["us", "us-quote", "forex", "crypto"]:
            raise ValueError("Endpoint is invalid")

        # Validate symbol list
        if len(symbols) == 0:
            raise ValueError("No symbol(s) provided")

        # Validate individual symbols
        prog = re.compile(r"^[A-z0-9-$]{1,48}$")
        for symbol in symbols:
            if not prog.match(symbol):
                raise ValueError(f"Symbol is invalid: {symbol}")

        # Validate max symbol subscriptions
        if len(symbols) > 50:
            raise ValueError("Max symbol subscription count is 50!")

        # Map class arguments to private variables
        self._api_key = api_key
        self._endpoint = endpoint
        self._symbols = symbols
        self._store_data = store_data
        self._display_stream = display_stream
        self._display_candle_1m = display_candle_1m
        self._display_candle_5m = display_candle_5m
        self._display_candle_1h = display_candle_1h

        self.running = True
        self.message = None
        self.stop_event = threading.Event()
        self.data_list = []
        self.ws = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        print("Stopping websocket...")
        self.running = False
        self.stop_event.set()
        self.thread.join()
        print("Websocket stopped.")

    def _floor_to_nearest_interval(self, timestamp_ms, interval):
        # Convert to seconds
        timestamp_s = timestamp_ms // 1000

        # Define the number of seconds for each interval
        seconds_per_minute = 60
        seconds_per_hour = seconds_per_minute * 60

        # Determine the number of seconds for the given interval
        if interval == "1 minute":
            interval_seconds = seconds_per_minute
        elif interval == "5 minutes":
            interval_seconds = 5 * seconds_per_minute
        elif interval == "1 hour":
            interval_seconds = seconds_per_hour
        else:
            raise ValueError(f"Unsupported interval: {interval}")

        # Floor to the nearest interval
        floored_s = (timestamp_s // interval_seconds) * interval_seconds

        # Convert back to milliseconds
        floored_ms = floored_s * 1000

        return floored_ms

    def _collect_data(self):
        self.ws = websocket.create_connection(f"wss://ws.eodhistoricaldata.com/ws/{self._endpoint}?api_token={self._api_key}")

        # Send the subscription message
        payload = {
            "action": "subscribe",
            "symbols": ",".join(self._symbols),
        }
        self.ws.send(json.dumps(payload))

        candle_1m = {}
        candle_5m = {}
        candle_1h = {}

        # Collect data until the stop event is set
        while not self.stop_event.is_set():
            self.message = self.ws.recv()
            message_json = json.loads(self.message)

            if self._store_data:
                self.data_list.append(self.message)

            if self._display_stream:
                print(self.message)

            if self._display_candle_1m:
                if "t" in message_json:
                    candle_date = self._floor_to_nearest_interval(message_json["t"], "1 minute")

                    if "t" in candle_1m and (candle_date != candle_1m["t"]):
                        print(candle_1m)

                        # New candle
                        candle_1m = {}

                    candle_1m["t"] = candle_date

                if "s" in message_json:
                    candle_1m["m"] = message_json["s"]
                    candle_1m["g"] = 60

                if "p" in message_json and "o" not in candle_1m:
                    # Forming candle
                    candle_1m["o"] = message_json["p"]
                    candle_1m["h"] = message_json["p"]
                    candle_1m["l"] = message_json["p"]
                    candle_1m["c"] = message_json["p"]
                    if "q" in message_json:
                        candle_1m["v"] = float(message_json["q"])
                elif "p" in message_json and "o" in candle_1m:
                    # Update candle
                    candle_1m["c"] = message_json["p"]

                    if message_json["p"] > candle_1m["h"]:
                        candle_1m["h"] = message_json["p"]

                    if message_json["p"] < candle_1m["l"]:
                        candle_1m["l"] = message_json["p"]

                    # Sum volume
                    if self._endpoint == 'cypto':
                        candle_1m["v"] += float(message_json["q"])

                # Uncomment this to see the candle forming
                # print(candle_1m)

            if self._display_candle_5m:
                if "t" in message_json:
                    candle_date = self._floor_to_nearest_interval(message_json["t"], "5 minutes")

                    if "t" in candle_5m and (candle_date != candle_5m["t"]):
                        print(candle_5m)

                        # New candle
                        candle_5m = {}

                    candle_5m["t"] = candle_date

                if "s" in message_json:
                    candle_5m["m"] = message_json["s"]
                    candle_5m["g"] = 60

                if "p" in message_json and "o" not in candle_5m:
                    # Forming candle
                    candle_5m["o"] = message_json["p"]
                    candle_5m["h"] = message_json["p"]
                    candle_5m["l"] = message_json["p"]
                    candle_5m["c"] = message_json["p"]
                    if "q" in message_json:
                        candle_5m["v"] = float(message_json["q"])
                elif "p" in message_json and "o" in candle_5m:
                    # Update candle
                    candle_5m["c"] = message_json["p"]

                    if message_json["p"] > candle_5m["h"]:
                        candle_5m["h"] = message_json["p"]

                    if message_json["p"] < candle_5m["l"]:
                        candle_5m["l"] = message_json["p"]

                    # Sum volume
                    if self._endpoint == 'cypto':
                        candle_5m["v"] += float(message_json["q"])

                # Uncomment this to see the candle forming
                # print(candle_5m)

            if self._display_candle_1h:
                if "t" in message_json:
                    candle_date = self._floor_to_nearest_interval(message_json["t"], "1 hour")

                    if "t" in candle_1h and (candle_date != candle_1h["t"]):
                        print(candle_1h)

                        # New candle
                        candle_1h = {}

                    candle_1h["t"] = candle_date

                if "s" in message_json:
                    candle_1h["m"] = message_json["s"]
                    candle_1h["g"] = 60

                if "p" in message_json and "o" not in candle_1h:
                    # Forming candle
                    candle_1h["o"] = message_json["p"]
                    candle_1h["h"] = message_json["p"]
                    candle_1h["l"] = message_json["p"]
                    candle_1h["c"] = message_json["p"]
                    if "q" in message_json:
                        candle_1h["v"] = float(message_json["q"])
                elif "p" in message_json and "o" in candle_1h:
                    # Update candle
                    candle_1h["c"] = message_json["p"]

                    if message_json["p"] > candle_1h["h"]:
                        candle_1h["h"] = message_json["p"]

                    if message_json["p"] < candle_1h["l"]:
                        candle_1h["l"] = message_json["p"]

                    # Sum volume
                    if self._endpoint == 'cypto':
                        candle_1h["v"] += float(message_json["q"])

                # Uncomment this to see the candle forming
                # print(candle_1h)

        # Close the WebSocket connection
        self.ws.close()

    def _keepalive(self, interval=30):
        if (self.ws is not None) and (hasattr(self.ws, "connected")):
            while self.ws.connected:
                self.ws.ping("keepalive")
                time.sleep(interval)

    def start(self):
        self.thread = threading.Thread(target=self._collect_data)
        self.keepalive = threading.Thread(target=self._keepalive)
        self.thread.start()
        self.keepalive.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join()
        self.keepalive.join()

    def get_data(self):
        return self.data_list


if __name__ == "__main__":
    client = WebSocketClient(
        api_key="OeAFFmMliFG5orCUuwAKQ8l4WWFQ67YX",
        endpoint="crypto",
        symbols=["BTC-USD"],
        display_stream=False,
        display_candle_1m=True,
        display_candle_5m=False,
        display_candle_1h=False,
    )
    client.start()

    try:
        while client.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping due to user request.")
        client.stop()
