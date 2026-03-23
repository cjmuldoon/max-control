"""Discord Admin — Create channels, manage the CONTROL server.

"Would you believe... automated server management?"

Uses the bot token to create channels, set up categories, and wire
everything together. Enables 99 to do full project setup including
Discord channel creation.
"""
import json
import os
import requests


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'discord_bot_config.json')


def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def _save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def _get_headers():
    config = _load_config()
    token = config.get('discord_token', '')
    return {
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json',
    }


def get_guilds():
    """Get all servers the bot is in."""
    resp = requests.get('https://discord.com/api/v10/users/@me/guilds', headers=_get_headers())
    if resp.status_code == 200:
        return resp.json()
    return []


def get_guild_channels(guild_id):
    """Get all channels in a server."""
    resp = requests.get(f'https://discord.com/api/v10/guilds/{guild_id}/channels', headers=_get_headers())
    if resp.status_code == 200:
        return resp.json()
    return []


def create_channel(guild_id, name, category_id=None, topic=None):
    """Create a text channel in a Discord server.

    Returns the channel ID on success.
    """
    payload = {
        'name': name,
        'type': 0,  # Text channel
    }
    if category_id:
        payload['parent_id'] = str(category_id)
    if topic:
        payload['topic'] = topic

    resp = requests.post(
        f'https://discord.com/api/v10/guilds/{guild_id}/channels',
        headers=_get_headers(),
        json=payload,
    )

    if resp.status_code in (200, 201):
        channel = resp.json()
        return {
            'success': True,
            'channel_id': channel['id'],
            'channel_name': channel['name'],
        }
    else:
        return {
            'success': False,
            'error': f'Discord API error {resp.status_code}: {resp.text[:200]}',
        }


def create_category(guild_id, name):
    """Create a channel category."""
    payload = {
        'name': name,
        'type': 4,  # Category
    }
    resp = requests.post(
        f'https://discord.com/api/v10/guilds/{guild_id}/channels',
        headers=_get_headers(),
        json=payload,
    )
    if resp.status_code in (200, 201):
        cat = resp.json()
        return {'success': True, 'category_id': cat['id'], 'name': cat['name']}
    return {'success': False, 'error': resp.text[:200]}


def setup_project_channel(project_name, project_slug, guild_id=None):
    """Create a Discord channel for a project.

    If no guild_id provided, uses the first server the bot is in.
    Returns channel_id for wiring into Max.
    """
    if not guild_id:
        guilds = get_guilds()
        if not guilds:
            return {'success': False, 'error': 'Bot is not in any Discord servers.'}
        guild_id = guilds[0]['id']

    # Check if a CONTROL category exists, create if not
    channels = get_guild_channels(guild_id)
    control_category = None
    for ch in channels:
        if ch['type'] == 4 and 'control' in ch['name'].lower():
            control_category = ch['id']
            break

    if not control_category:
        result = create_category(guild_id, 'CONTROL Operations')
        if result['success']:
            control_category = result['category_id']

    # Check if channel already exists
    channel_name = project_slug.lower().replace('_', '-')
    for ch in channels:
        if ch['name'] == channel_name:
            return {
                'success': True,
                'channel_id': ch['id'],
                'channel_name': ch['name'],
                'already_existed': True,
            }

    # Create the channel
    result = create_channel(
        guild_id,
        channel_name,
        category_id=control_category,
        topic=f'CONTROL operations for {project_name} — monitored by Agent 86',
    )

    if result['success']:
        # Save channel mapping in config
        config = _load_config()
        if 'channels' not in config:
            config['channels'] = {}
        config['channels'][project_slug] = result['channel_id']
        _save_config(config)

    return result


def setup_agent99_channel(guild_id=None):
    """Create the #agent-99 channel."""
    if not guild_id:
        guilds = get_guilds()
        if not guilds:
            return {'success': False, 'error': 'Bot is not in any servers.'}
        guild_id = guilds[0]['id']

    channels = get_guild_channels(guild_id)
    control_category = None
    for ch in channels:
        if ch['type'] == 4 and 'control' in ch['name'].lower():
            control_category = ch['id']
            break

    # Check if already exists
    for ch in channels:
        if ch['name'] == 'agent-99':
            return {'success': True, 'channel_id': ch['id'], 'already_existed': True}

    return create_channel(
        guild_id,
        'agent-99',
        category_id=control_category,
        topic="Agent 99's direct line — CONTROL's most competent operative",
    )
