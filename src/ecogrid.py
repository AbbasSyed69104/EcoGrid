"""
EcoGrid Energy - ICT711 Assessment 2
Group MEL 7
1. Uday Sagar Chandel - 70324
2. Parthsinh Jashvantsinh Chauhan - 67104
3. Abbas Syed - 69104

Prototype flow:
Smart Meter -> Smart Meter Integration -> Event Bus ->
Marketplace -> Trade Event -> Financial Settlement
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4
import csv
import json
import logging


BASE = Path(__file__).resolve().parent.parent
RESULTS = BASE / "results"
LOGS = BASE / "logs"
RESULTS.mkdir(exist_ok=True)
LOGS.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOGS / "ecogrid.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def now():
    return datetime.now(timezone.utc).isoformat()


class EventType(str, Enum):
    ENERGY_AVAILABLE = "EnergyAvailable"
    TRADE_CREATED = "TradeCreated"
    SETTLEMENT_COMPLETED = "SettlementCompleted"


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: EventType
    timestamp: str
    payload: dict


class EventBus:
    """Lightweight event bus used to demonstrate asynchronous boundaries."""

    def __init__(self):
        self.subscribers = {}
        self.processed = set()
        self.history = []

    def subscribe(self, event_type, handler):
        self.subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event):
        if event.event_id in self.processed:
            logging.warning("Duplicate event ignored: %s", event.event_id)
            return
        self.processed.add(event.event_id)
        self.history.append(event)
        logging.info("Published %s", event.event_type.value)
        for handler in self.subscribers.get(event.event_type, []):
            handler(event)

    def make_event(self, event_type, payload):
        return Event(str(uuid4()), event_type, now(), payload)


@dataclass
class MeterReading:
    meter_id: str
    owner_id: str
    generated_kwh: float
    consumed_kwh: float
    timestamp: str

    @property
    def excess_kwh(self):
        return round(max(self.generated_kwh - self.consumed_kwh, 0), 3)


class SmartMeterIntegration:
    """Validates, normalises and publishes useful IoT meter information."""

    def __init__(self, bus):
        self.bus = bus

    @staticmethod
    def validate(meter_id, owner_id, generated, consumed):
        if not meter_id.strip():
            return False, "Meter ID is required"
        if not owner_id.strip():
            return False, "Owner ID is required"
        if generated < 0 or consumed < 0:
            return False, "Energy values cannot be negative"
        return True, "Valid"

    def ingest(self, meter_id, owner_id, generated, consumed):
        valid, message = self.validate(meter_id, owner_id, generated, consumed)
        if not valid:
            print("[Smart Meter] REJECTED:", message)
            logging.warning(message)
            return None

        reading = MeterReading(
            meter_id.strip(), owner_id.strip(),
            round(float(generated), 3),
            round(float(consumed), 3),
            now()
        )

        print(
            f"[Smart Meter] {reading.meter_id}: "
            f"{reading.excess_kwh:.2f} kWh excess energy"
        )

        if reading.excess_kwh > 0:
            event = self.bus.make_event(
                EventType.ENERGY_AVAILABLE,
                {
                    "meter_id": reading.meter_id,
                    "seller_id": reading.owner_id,
                    "available_kwh": reading.excess_kwh,
                },
            )
            self.bus.publish(event)
        return reading


@dataclass
class EnergyOffer:
    offer_id: str
    seller_id: str
    available_kwh: float
    price_per_kwh: float
    status: str = "OPEN"


class Marketplace:
    """Matches buyer requests with available seller offers."""

    RATE = 0.25

    def __init__(self, bus):
        self.bus = bus
        self.offers = {}
        self.trades = {}
        bus.subscribe(EventType.ENERGY_AVAILABLE, self.create_offer)

    def create_offer(self, event):
        p = event.payload
        offer = EnergyOffer(
            str(uuid4()), p["seller_id"],
            float(p["available_kwh"]), self.RATE
        )
        self.offers[offer.offer_id] = offer
        print(
            f"[Marketplace] Offer {offer.offer_id[:8]}: "
            f"{offer.available_kwh:.2f} kWh @ ${offer.price_per_kwh:.2f}/kWh"
        )

    def buy(self, buyer_id, requested_kwh):
        if not buyer_id.strip() or requested_kwh <= 0:
            print("[Marketplace] Invalid buyer or quantity")
            return None

        for offer in self.offers.values():
            if offer.status != "OPEN" or offer.seller_id == buyer_id:
                continue
            if offer.available_kwh < requested_kwh:
                continue

            amount = round(requested_kwh * offer.price_per_kwh, 2)
            trade = {
                "trade_id": str(uuid4()),
                "offer_id": offer.offer_id,
                "seller_id": offer.seller_id,
                "buyer_id": buyer_id,
                "energy_kwh": requested_kwh,
                "amount": amount,
                "timestamp": now(),
                "status": "CREATED",
            }

            offer.available_kwh = round(
                offer.available_kwh - requested_kwh, 3
            )
            if offer.available_kwh == 0:
                offer.status = "CLOSED"

            self.trades[trade["trade_id"]] = trade
            self.bus.publish(
                self.bus.make_event(EventType.TRADE_CREATED, trade)
            )
            print(
                f"[Marketplace] Trade {trade['trade_id'][:8]} "
                f"created for ${amount:.2f}"
            )
            return trade

        print("[Marketplace] No suitable offer found")
        return None


class FinancialSettlement:
    """Processes trade events independently from marketplace logic."""

    def __init__(self, bus):
        self.bus = bus
        self.settlements = {}
        bus.subscribe(EventType.TRADE_CREATED, self.settle)

    def settle(self, event):
        trade = event.payload
        trade_id = trade["trade_id"]

        if trade_id in self.settlements:
            return

        settlement = {
            "settlement_id": str(uuid4()),
            "trade_id": trade_id,
            "seller_id": trade["seller_id"],
            "buyer_id": trade["buyer_id"],
            "amount": trade["amount"],
            "currency": "USD",
            "status": "COMPLETED",
            "timestamp": now(),
        }

        self.settlements[trade_id] = settlement
        self.bus.publish(
            self.bus.make_event(
                EventType.SETTLEMENT_COMPLETED, settlement
            )
        )
        print(
            f"[Settlement] {settlement['settlement_id'][:8]} "
            f"completed: ${settlement['amount']:.2f}"
        )


def save_results(bus, settlement):
    with (RESULTS / "event_history.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "event_type", "timestamp", "payload"])
        for e in bus.history:
            writer.writerow([
                e.event_id, e.event_type.value, e.timestamp,
                json.dumps(e.payload)
            ])

    with (RESULTS / "settlements.csv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        fields = [
            "settlement_id", "trade_id", "seller_id", "buyer_id",
            "amount", "currency", "status", "timestamp"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(settlement.settlements.values())


def run_demo():
    print("=" * 65)
    print("ECOGRID ENERGY - ICT711 ARCHITECTURE PROTOTYPE")
    print("=" * 65)

    bus = EventBus()
    meter = SmartMeterIntegration(bus)
    marketplace = Marketplace(bus)
    settlement = FinancialSettlement(bus)

    print("\n1. SMART METER INGESTION")
    meter.ingest("SM-001", "SELLER-001", 10.5, 4.0)

    print("\n2. BUYER REQUEST")
    marketplace.buy("BUYER-001", 3.0)

    print("\n3. VALIDATION TEST")
    meter.ingest("SM-002", "SELLER-002", -2.0, 1.0)

    save_results(bus, settlement)

    print("\n4. SYSTEM SUMMARY")
    print("Events processed :", len(bus.history))
    print("Offers created   :", len(marketplace.offers))
    print("Trades created   :", len(marketplace.trades))
    print("Settlements      :", len(settlement.settlements))
    print("\nResults saved to:", RESULTS)
    print("Log saved to    :", LOGS / "ecogrid.log")


if __name__ == "__main__":
    run_demo()
