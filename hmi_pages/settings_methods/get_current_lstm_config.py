# hmi_pages/settings_methods/get_current_lstm_config.py

from root.config import load_app_config

def get_current_lstm_config():
    app_cfg = load_app_config()
    return app_cfg.get('lstm_config', {
        'epochs': 50,
        'batch_size': 32,
        'learning_rate': 0.001,
        'lstm_units': 64,
        'dropout_rate': 0.2,
        'optimizer': 'Adam',
    })
