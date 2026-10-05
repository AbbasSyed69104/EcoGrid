# ICT711 EcoGrid Energy Prototype - MEL 7

**Group members**
1. Uday Sagar Chandel - 70324
2. Parthsinh Jashvantsinh Chauhan - 67104
3. Abbas Syed - 69104

## Architecture Demonstrated

Smart Meter Integration -> Event Bus -> Marketplace -> Trade Event -> Financial Settlement

The prototype models the three EcoGrid bounded contexts:
- Smart Meter Integration
- Marketplace
- Financial Settlement

It demonstrates validation, event-driven communication, idempotent event handling, trade matching, settlement processing, CSV persistence and logging.

## Run

```bash
python src/ecogrid.py
```

## Test

```bash
python -m unittest discover -s tests -v
```

No third-party packages are required.
