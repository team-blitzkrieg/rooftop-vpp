"""Optional MQTT bridge.

Set MQTT_URL (for example mqtt://mosquitto:1883) to subscribe. Leave it empty
and this module does nothing. Messages are readings, not commands.

Topic: rooftop/reading
Payload: {"device_token", "timestamp", "pv_kw", "consumption_kw"}
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

TOPIC = "rooftop/reading"


def parse_payload(payload: bytes | str) -> dict:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    body = json.loads(payload)
    if not isinstance(body, dict) or "timestamp" not in body:
        raise ValueError("MQTT payload needs a timestamp")
    if "device_token" not in body:
        raise ValueError("MQTT payload needs a device_token")
    return body


def start_bridge(mqtt_url: str, on_message) -> object | None:
    """Subscribe in the background. Returns None when the URL is empty."""
    if not mqtt_url:
        logger.info("MQTT bridge is off.")
        return None
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def _on_message(_client, _userdata, message):
        try:
            body = parse_payload(message.payload)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Dropped MQTT message: %s", exc)
            return
        on_message(body)

    client.on_message = _on_message
    client.connect(mqtt_url.replace("mqtt://", "").split(":")[0], _port(mqtt_url))
    client.subscribe(TOPIC)
    client.loop_start()
    logger.info("MQTT bridge subscribed to %s", TOPIC)
    return client


def _port(url: str) -> int:
    host = url.replace("mqtt://", "")
    if ":" not in host:
        return 1883
    return int(host.rsplit(":", 1)[1])
