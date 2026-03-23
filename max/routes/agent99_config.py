"""Agent 99 Bot Configuration — connect 99 to Discord/Telegram."""
import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from max.services.agent99_bot import agent99_bot
from max.services.agent99 import agent99
from max.utils.smart_quotes import get_quote

agent99_config_bp = Blueprint('agent99_config', __name__)

CONFIG_FILE = None


def _get_config_path():
    global CONFIG_FILE
    if CONFIG_FILE is None:
        from flask import current_app
        CONFIG_FILE = os.path.join(os.path.dirname(current_app.config['DB_PATH']), 'agent99_bots.json')
    return CONFIG_FILE


def _load_config():
    path = _get_config_path()
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {'discord': {}, 'telegram': {}}


def _save_config(config):
    with open(_get_config_path(), 'w') as f:
        json.dump(config, f, indent=2)


@agent99_config_bp.route('/')
def index():
    config = _load_config()
    return render_template(
        'agent99_config.html',
        config=config,
        discord_running=agent99_bot.is_discord_running(),
        telegram_running=agent99_bot.is_telegram_running(),
    )


@agent99_config_bp.route('/discord/configure', methods=['POST'])
def configure_discord():
    token = request.form.get('token', '').strip()
    channel_id = request.form.get('channel_id', '').strip()

    if not token:
        flash("Need a bot token, Chief.", 'error')
        return redirect(url_for('agent99_config.index'))

    config = _load_config()
    config['discord'] = {'token': token, 'channel_id': channel_id}
    _save_config(config)

    flash(f'Discord configured for 99. {get_quote("success")}', 'success')
    return redirect(url_for('agent99_config.index'))


@agent99_config_bp.route('/telegram/configure', methods=['POST'])
def configure_telegram():
    token = request.form.get('token', '').strip()
    chat_id = request.form.get('chat_id', '').strip()

    if not token:
        flash("Need a bot token, Chief.", 'error')
        return redirect(url_for('agent99_config.index'))

    config = _load_config()
    config['telegram'] = {'token': token, 'chat_id': chat_id}
    _save_config(config)

    flash(f'Telegram configured for 99. {get_quote("success")}', 'success')
    return redirect(url_for('agent99_config.index'))


@agent99_config_bp.route('/discord/toggle', methods=['POST'])
def toggle_discord():
    if agent99_bot.is_discord_running():
        agent99_bot.stop_discord()
        flash('99 disconnected from Discord.', 'success')
    else:
        config = _load_config()
        dc = config.get('discord', {})
        if not dc.get('token'):
            flash("Configure Discord first, Chief.", 'error')
            return redirect(url_for('agent99_config.index'))
        try:
            agent99_bot.start_discord(dc['token'], dc.get('channel_id'))
            flash(f'99 is now on Discord! {get_quote("comms")}', 'success')
        except Exception as e:
            flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('agent99_config.index'))


@agent99_config_bp.route('/telegram/toggle', methods=['POST'])
def toggle_telegram():
    if agent99_bot.is_telegram_running():
        agent99_bot.stop_telegram()
        flash('99 disconnected from Telegram.', 'success')
    else:
        config = _load_config()
        tg = config.get('telegram', {})
        if not tg.get('token'):
            flash("Configure Telegram first, Chief.", 'error')
            return redirect(url_for('agent99_config.index'))
        try:
            agent99_bot.start_telegram(tg['token'], tg.get('chat_id'))
            flash(f'99 is now on Telegram! {get_quote("comms")}', 'success')
        except Exception as e:
            flash(f'Sorry about that, Chief. {e}', 'error')

    return redirect(url_for('agent99_config.index'))


@agent99_config_bp.route('/log')
def log():
    """View 99's conversation log — full permanent history."""
    entries = agent99.get_log(limit=500)
    return render_template('agent99_log.html', entries=entries)


@agent99_config_bp.route('/log/json')
def log_json():
    """JSON API for 99's log."""
    limit = int(request.args.get('limit', 200))
    return jsonify(agent99.get_log(limit=limit))
