"""Internal API — used by 99 and agents to orchestrate CONTROL operations.

"99 just calls the API, Chief. 86 does the rest."
"""
import os
import uuid
import json
from flask import Blueprint, request, jsonify, current_app
from max.models.project import Project
from max.models.bot_config import BotConfig

api_bp = Blueprint('api', __name__)


@api_bp.route('/quick-create', methods=['POST'])
def quick_create():
    """Create a project with everything set up in one call.

    Accepts JSON:
    {
        "name": "jira-dashboard",
        "location": "work",          # "work" or "local"
        "description": "JIRA roadmap dashboard for SLT meetings",
        "github_url": "",            # optional
        "create_discord": true,      # create a Discord channel
        "schedule_health": true,     # daily 6pm health check
        "scaffold": "flask",         # optional: scaffold a flask app
        "assigned_to": "86 (Opus)",  # optional: assign to an agent
        "scheduled_at": "2026-03-24T09:00",  # optional: when to start work
        "feedback_items": [          # optional: seed the feedback register
            {"title": "Build roadmap view", "category": "feature_request", "priority": "high"}
        ]
    }
    """
    data = request.get_json() or {}

    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Need a project name, Chief.'}), 400

    location = data.get('location', 'local')
    description = data.get('description', '')
    github_url = data.get('github_url', '')

    # Determine path
    locations = current_app.config['PROJECT_LOCATIONS']
    base = locations.get(location, locations.get('local', ''))
    slug = Project.slugify(name)
    path = os.path.join(base, slug)

    # Create directory
    os.makedirs(path, exist_ok=True)

    # Register project
    try:
        project = Project.create(
            name=name, path=path, location_type=location,
            description=description, github_url=github_url,
        )
    except Exception as e:
        return jsonify({'error': f'Failed to create project: {e}'}), 500

    result = {
        'project_id': project.id,
        'slug': project.slug,
        'path': path,
        'created': True,
    }

    # Scaffold Flask app
    if data.get('scaffold') == 'flask':
        _scaffold_flask(path, name)
        result['scaffolded'] = 'flask'

    # Create Discord channel
    if data.get('create_discord'):
        try:
            from max.services.discord_admin import setup_project_channel
            dc_result = setup_project_channel(name, slug)
            if dc_result.get('success'):
                channel_id = dc_result['channel_id']
                # Load bot token from config
                config_path = os.path.join(os.path.dirname(current_app.config['DB_PATH']), 'discord_bot_config.json')
                if os.path.exists(config_path):
                    with open(config_path) as f:
                        bot_config = json.load(f)
                    token = bot_config.get('discord_token', '')
                    if token:
                        BotConfig.create(project.id, 'discord', token, channel_id)
                        # Update channel map in config
                        bot_config.setdefault('channels', {})[slug] = channel_id
                        with open(config_path, 'w') as f:
                            json.dump(bot_config, f, indent=2)
                result['discord_channel'] = channel_id
        except Exception as e:
            result['discord_error'] = str(e)

    # Schedule health check
    if data.get('schedule_health'):
        from max.db.connection import get_db
        db = get_db()
        db.execute(
            '''INSERT INTO schedules (id, project_id, name, cron_expression, task_type, enabled)
               VALUES (?, ?, ?, ?, ?, 1)''',
            (str(uuid.uuid4()), project.id, f'Daily Health — {name}', '0 18 * * *', 'health_check'),
        )
        db.commit()
        result['health_scheduled'] = True

    # Seed feedback items — inherit agent assignment and schedule from project
    if data.get('feedback_items'):
        from max.services.feedback_register import feedback_register
        assigned = data.get('assigned_to', '')
        scheduled = data.get('scheduled_at', '')
        for item in data['feedback_items']:
            item_id = feedback_register.add_item(
                project.id,
                item.get('title', ''),
                item.get('description', ''),
                item.get('category', 'feature_request'),
                item.get('priority', 'medium'),
            )
            if assigned or scheduled:
                feedback_register.update_item(
                    item_id,
                    assigned_to=item.get('assigned_to', assigned),
                    scheduled_at=item.get('scheduled_at', scheduled),
                )
        result['feedback_items_added'] = len(data['feedback_items'])

    # Assign and schedule work
    if data.get('assigned_to') or data.get('scheduled_at'):
        from max.services.feedback_register import feedback_register
        # Create a main task for this project
        item_id = feedback_register.add_item(
            project.id,
            f'Build {name}',
            description,
            'feature_request',
            'high',
        )
        feedback_register.update_item(
            item_id,
            assigned_to=data.get('assigned_to'),
            scheduled_at=data.get('scheduled_at'),
        )
        result['work_scheduled'] = {
            'assigned_to': data.get('assigned_to'),
            'scheduled_at': data.get('scheduled_at'),
        }

    return jsonify(result)


@api_bp.route('/projects', methods=['GET'])
def list_projects():
    """List all projects."""
    projects = Project.get_all()
    return jsonify([p.to_dict() for p in projects])


def _scaffold_flask(path, name):
    """Scaffold a basic Flask app structure."""
    dirs = ['static/css', 'static/js', 'static/img', 'templates', 'models', 'views', 'services', 'infrastructure']
    for d in dirs:
        os.makedirs(os.path.join(path, d), exist_ok=True)

    # app.py
    with open(os.path.join(path, 'app.py'), 'w') as f:
        f.write(f'''"""{ name } — Flask Application"""
import flask

app = flask.Flask(__name__)
app.secret_key = '{uuid.uuid4().hex}'

@app.route('/')
def index():
    return flask.render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
''')

    # templates/index.html
    with open(os.path.join(path, 'templates', 'index.html'), 'w') as f:
        f.write(f'''<!DOCTYPE html>
<html><head><title>{name}</title></head>
<body><h1>{name}</h1><p>Ready for development.</p></body>
</html>
''')

    # requirements.txt
    with open(os.path.join(path, 'requirements.txt'), 'w') as f:
        f.write('flask>=3.1\n')

    # CLAUDE.md
    with open(os.path.join(path, 'CLAUDE.md'), 'w') as f:
        f.write(f'# {name}\n\nFlask web application.\n')
