# hmi_pages/settings_methods/get_available_assets.py

import os, json, MetaTrader5 as mt5
from datetime import datetime, timedelta
from root import config as cfg

SYMBOLS_DIR_PATH = os.path.join(cfg.DB_DIR, "symbols_directory.json")

def get_available_assets():
    """Обновляет справочник MT5 раз в неделю, YFinance — статика."""
    data = {
        "mt5": {"symbols": [], "timeframes": ["M15", "H1", "H4", "D1"]},
        "yfinance": {
            "symbols": ["BTC-USD","ETH-USD","EURUSD=X","GBPUSD=X","GC=F","AAPL","NVDA"], 
            "timeframes": ["H1", "D1"]
        },
        "last_update": "2000-01-01"
    }
    
    if os.path.exists(SYMBOLS_DIR_PATH):
        try:
            with open(SYMBOLS_DIR_PATH, "r") as f:
                data = json.load(f)
            last_dt = datetime.strptime(data.get("last_update"), "%Y-%m-%d")
            if datetime.now() - last_dt < timedelta(days=7): return data
        except: pass

    if mt5.initialize():
        syms = sorted([s.name for s in mt5.symbols_get() if s.visible])
        data["mt5"]["symbols"] = syms
        data["last_update"] = datetime.now().strftime("%Y-%m-%d")
        with open(SYMBOLS_DIR_PATH, "w") as f: 
            json.dump(data, f, indent=4)
        mt5.shutdown()
    return data
