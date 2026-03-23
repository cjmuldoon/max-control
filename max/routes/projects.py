import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from max.models.project import Project
from max.utils.smart_quotes import get_quote

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/create', methods=['GET', 'POST'])
def create():
    """Deploy a new agent to the field."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        location_type = request.form.get('location_type', 'local')
        description = request.form.get('description', '').strip()
        github_url = request.form.get('github_url', '').strip()
        notion_page_id = request.form.get('notion_page_id', '').strip()
        use_existing = request.form.get('use_existing') == 'on'
        existing_path = request.form.get('existing_path', '').strip()

        if not name:
            flash("Sorry about that, Chief. We need a project name.", 'error')
            return redirect(url_for('projects.create'))

        # Determine project path
        if use_existing and existing_path:
            path = existing_path
            if not os.path.isdir(path):
                flash("Missed it by that much! That directory doesn't exist.", 'error')
                return redirect(url_for('projects.create'))
        else:
            base = current_app.config['PROJECT_LOCATIONS'].get(location_type, '')
            if not base:
                flash("Sorry about that, Chief. Unknown location type.", 'error')
                return redirect(url_for('projects.create'))
            slug = Project.slugify(name)
            path = os.path.join(base, slug)

            # Create directory if it doesn't exist
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

        try:
            project = Project.create(
                name=name,
                path=path,
                location_type=location_type,
                description=description,
                github_url=github_url,
                notion_page_id=notion_page_id,
            )
            flash(f'Agent deployed! Project "{name}" is ready. {get_quote("success")}', 'success')
            return redirect(url_for('projects.detail', slug=project.slug))
        except Exception as e:
            flash(f'Sorry about that, Chief. {e}', 'error')
            return redirect(url_for('projects.create'))

    locations = current_app.config['PROJECT_LOCATIONS']
    return render_template('project_create.html', locations=locations)


@projects_bp.route('/<slug>')
def detail(slug):
    """Project detail — Agent 86's dossier."""
    project = Project.get_by_slug(slug)
    if not project:
        flash("That agent doesn't exist. KAOS must have intercepted them.", 'error')
        return redirect(url_for('main.launchpad'))

    agent = project.get_agent()
    return render_template('project_detail.html', project=project, agent=agent)


@projects_bp.route('/<slug>/edit', methods=['POST'])
def edit(slug):
    project = Project.get_by_slug(slug)
    if not project:
        flash("Agent not found.", 'error')
        return redirect(url_for('main.launchpad'))

    project.update(
        name=request.form.get('name', project.name),
        description=request.form.get('description', project.description),
        github_url=request.form.get('github_url', project.github_url),
        notion_page_id=request.form.get('notion_page_id', project.notion_page_id),
    )
    flash(f'Project updated. {get_quote("success")}', 'success')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/<slug>/brief', methods=['POST'])
def update_brief(slug):
    """Update the full mission brief for a project."""
    project = Project.get_by_slug(slug)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    project.update(
        brief=request.form.get('brief', ''),
        tech_stack=request.form.get('tech_stack', ''),
        environments_info=request.form.get('environments_info', ''),
        conventions=request.form.get('conventions', ''),
        description=request.form.get('description', project.description),
    )
    flash(f'Mission brief updated. {get_quote("success")}', 'success')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/<slug>/claude-md')
def view_claude_md(slug):
    """View the current CLAUDE.md for a project."""
    project = Project.get_by_slug(slug)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    claude_md_path = os.path.join(project.path, 'CLAUDE.md')
    content = ''
    if os.path.exists(claude_md_path):
        with open(claude_md_path) as f:
            content = f.read()

    return render_template('claude_md_viewer.html', project=project, content=content)


@projects_bp.route('/<slug>/generate-claude-md', methods=['POST'])
def generate_claude_md(slug):
    """Generate CLAUDE.md from the project brief."""
    project = Project.get_by_slug(slug)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    claude_md_path = os.path.join(project.path, 'CLAUDE.md')

    # Read existing content
    existing = ''
    if os.path.exists(claude_md_path):
        with open(claude_md_path) as f:
            existing = f.read()

    # Build the CONTROL Brief section from Max's fields
    brief_parts = []
    if project.description:
        brief_parts.append(f'**Description:** {project.description}')
    if project.brief:
        brief_parts.append(f'\n{project.brief}')
    if project.tech_stack:
        brief_parts.append(f'\n**Tech Stack:** {project.tech_stack}')
    if project.conventions:
        brief_parts.append(f'\n**Conventions:** {project.conventions}')
    if project.environments_info:
        brief_parts.append(f'\n**Environments:** {project.environments_info}')
    if project.github_url:
        brief_parts.append(f'\n**Repository:** {project.github_url}')

    control_section = '## CONTROL Brief\n\n' + '\n'.join(brief_parts) + '\n'

    # Merge: preserve existing, update/append CONTROL Brief section
    marker_start = '## CONTROL Brief'
    if marker_start in existing:
        # Find the CONTROL Brief section and replace it
        import re
        # Match from ## CONTROL Brief to the next ## heading or end of file
        pattern = r'## CONTROL Brief\n.*?(?=\n## |\Z)'
        updated = re.sub(pattern, control_section.strip(), existing, flags=re.DOTALL)
    elif existing.strip():
        # Append to existing file
        updated = existing.rstrip() + '\n\n' + control_section
    else:
        # No existing file — create with header + brief
        updated = f'# {project.name}\n\n' + control_section

    with open(claude_md_path, 'w') as f:
        f.write(updated)

    flash(f'CLAUDE.md updated — CONTROL Brief section {"replaced" if marker_start in existing else "appended"}. {get_quote("success")}', 'success')
    return redirect(url_for('projects.view_claude_md', slug=project.slug))


@projects_bp.route('/<slug>/delete', methods=['POST'])
def delete(slug):
    project = Project.get_by_slug(slug)
    if not project:
        flash("Agent not found.", 'error')
        return redirect(url_for('main.launchpad'))

    project.delete()
    flash(f'Project "{project.name}" removed from CONTROL. {get_quote("agent_stop")}', 'success')
    return redirect(url_for('main.launchpad'))


@projects_bp.route('/scan')
def scan():
    """Scan project directories for unregistered projects.

    "Agent 86 is surveilling the area."
    Supports search, location filter, sort modes, time grouping, and undercover hiding.
    """
    from datetime import datetime, timedelta
    import sqlite3

    locations = current_app.config['PROJECT_LOCATIONS']
    existing_paths = {p.path for p in Project.get_all()}
    search_query = request.args.get('q', '').strip().lower()
    location_filter = request.args.get('location', '')
    sort_by = request.args.get('sort', 'modified')  # modified, name, size
    show_undercover = request.args.get('undercover', '') == '1'

    # Get undercover paths
    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path)
    undercover_paths = {row[0] for row in conn.execute('SELECT path FROM undercover_paths').fetchall()}
    conn.close()

    discovered = []

    for loc_type, base_path in locations.items():
        if location_filter and loc_type != location_filter:
            continue
        if not os.path.isdir(base_path):
            continue
        for entry in os.scandir(base_path):
            if entry.is_dir() and not entry.name.startswith('.'):
                if entry.path in existing_paths:
                    continue

                is_undercover = entry.path in undercover_paths
                if is_undercover and not show_undercover:
                    continue

                name = entry.name.replace('-', ' ').replace('_', ' ').title()

                if search_query and search_query not in name.lower() and search_query not in entry.name.lower():
                    continue

                # Get modification time
                try:
                    mtime = os.path.getmtime(entry.path)
                    modified = datetime.fromtimestamp(mtime)
                except Exception:
                    modified = datetime.min
                    mtime = 0

                # Get dir size (quick — top-level only)
                try:
                    size = sum(
                        e.stat().st_size for e in os.scandir(entry.path) if e.is_file()
                    )
                except Exception:
                    size = 0

                has_git = os.path.isdir(os.path.join(entry.path, '.git'))
                has_readme = os.path.exists(os.path.join(entry.path, 'README.md'))

                discovered.append({
                    'name': name,
                    'path': entry.path,
                    'location_type': loc_type,
                    'has_git': has_git,
                    'has_readme': has_readme,
                    'modified': modified,
                    'modified_ts': mtime,
                    'modified_str': modified.strftime('%d %b %Y'),
                    'size': size,
                    'size_str': _format_size(size),
                    'is_undercover': is_undercover,
                })

    # Sort
    if sort_by == 'name':
        discovered.sort(key=lambda x: x['name'].lower())
    elif sort_by == 'size':
        discovered.sort(key=lambda x: x['size'], reverse=True)
    else:  # modified (default)
        discovered.sort(key=lambda x: x['modified_ts'], reverse=True)

    # Group by time period (only for modified sort)
    groups = None
    if sort_by == 'modified':
        now = datetime.now()
        groups = _group_by_time(discovered, now)

    undercover_count = len(undercover_paths - existing_paths)

    return render_template(
        'partials/scan_results.html',
        discovered=discovered,
        groups=groups,
        search_query=search_query,
        sort_by=sort_by,
        show_undercover=show_undercover,
        undercover_count=undercover_count,
    )


@projects_bp.route('/undercover', methods=['POST'])
def toggle_undercover():
    """Mark/unmark paths as undercover — hide them from reconnaissance."""
    import sqlite3
    import uuid

    paths = request.form.getlist('paths')
    action = request.form.get('action', 'hide')  # hide or reveal

    if not paths:
        return jsonify({'error': 'No paths provided'}), 400

    db_path = current_app.config['DB_PATH']
    conn = sqlite3.connect(db_path)

    if action == 'hide':
        for path in paths:
            try:
                conn.execute(
                    'INSERT OR IGNORE INTO undercover_paths (id, path) VALUES (?, ?)',
                    (str(uuid.uuid4()), path),
                )
            except Exception:
                pass
        conn.commit()
        msg = f'{len(paths)} target(s) sent undercover.'
    else:
        placeholders = ','.join('?' * len(paths))
        conn.execute(f'DELETE FROM undercover_paths WHERE path IN ({placeholders})', paths)
        conn.commit()
        msg = f'{len(paths)} target(s) brought back from undercover.'

    conn.close()
    return jsonify({'message': msg, 'count': len(paths)})


@projects_bp.route('/quick-create', methods=['GET', 'POST'])
def quick_create():
    """Quick Deploy — full operation setup in one go.

    "Would you believe... a complete deployment in 30 seconds?"
    """
    if request.method == 'GET':
        return render_template('quick_create.html')

    name = request.form.get('name', '').strip()
    if not name:
        flash("Need an operation codename, Chief.", 'error')
        return redirect(url_for('projects.quick_create'))

    location_type = request.form.get('location_type', 'local')
    description = request.form.get('description', '').strip()
    github_url = request.form.get('github_url', '').strip()
    model = request.form.get('model', 'sonnet')
    permission_mode = request.form.get('permission_mode', 'plan')
    start_agent = request.form.get('start_agent') == 'on'

    # Step 1: Create project
    base = current_app.config['PROJECT_LOCATIONS'].get(location_type, '')
    slug = Project.slugify(name)
    path = os.path.join(base, slug)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

    try:
        project = Project.create(
            name=name, path=path, location_type=location_type,
            description=description, github_url=github_url,
        )
    except Exception as e:
        flash(f'Sorry about that, Chief. {e}', 'error')
        return redirect(url_for('projects.quick_create'))

    results = [f'Project "{name}" created']

    # Step 2: Start agent
    if start_agent:
        try:
            from max.services.agent_runner import agent_runner
            agent_runner.start_agent(project, model=model, permission_mode=permission_mode)
            results.append('Agent deployed')
        except Exception as e:
            results.append(f'Agent failed: {e}')

    # Step 3: Schedules
    import uuid as _uuid
    from max.db.connection import get_db
    db = get_db()

    if request.form.get('schedule_health') == 'on':
        db.execute(
            '''INSERT INTO schedules (id, project_id, name, cron_expression, task_type, enabled)
               VALUES (?, ?, ?, ?, ?, 1)''',
            (str(_uuid.uuid4()), project.id, f'Daily Health — {name}', '0 18 * * *', 'health_check'),
        )
        results.append('Health check scheduled (6pm daily)')

    if request.form.get('schedule_vuln') == 'on':
        db.execute(
            '''INSERT INTO schedules (id, project_id, name, cron_expression, task_type, enabled)
               VALUES (?, ?, ?, ?, ?, 1)''',
            (str(_uuid.uuid4()), project.id, f'Weekly Vuln Scan — {name}', '0 0 * * 0', 'vuln_scan'),
        )
        results.append('Vuln scan scheduled (Sunday midnight)')

    db.commit()

    # Step 4: Roadmap sync
    if request.form.get('sync_roadmap') == 'on':
        try:
            from max.services.roadmap import roadmap_service
            roadmap_service.sync_roadmap(project.id)
            results.append('Roadmap synced')
        except Exception:
            results.append('Roadmap sync skipped')

    # Step 5: Bots
    discord_token = request.form.get('discord_token', '').strip()
    telegram_token = request.form.get('telegram_token', '').strip()

    if discord_token:
        from max.models.bot_config import BotConfig
        BotConfig.create(project.id, 'discord', discord_token)
        results.append('Discord bot configured')

    if telegram_token:
        from max.models.bot_config import BotConfig
        BotConfig.create(project.id, 'telegram', telegram_token)
        results.append('Telegram bot configured')

    flash(f'Operation deployed! {", ".join(results)}. {get_quote("success")}', 'success')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/multi-launch', methods=['POST'])
def multi_launch():
    """Launch agents for multiple projects at once.

    "86, you're going to be busy."
    """
    project_ids = request.form.getlist('project_ids')
    model = request.form.get('model', 'sonnet')
    action = request.form.get('action', 'start')

    if not project_ids:
        flash("No operations selected, Chief.", 'error')
        return redirect(url_for('main.launchpad'))

    from max.services.agent_runner import agent_runner
    from max.models.agent import Agent

    results = []
    for pid in project_ids:
        project = Project.get_by_id(pid)
        if not project:
            continue

        try:
            if action == 'start':
                existing = Agent.get_by_project(pid)
                if existing and existing.status == 'running':
                    results.append(f'{project.name}: already running')
                    continue
                agent_runner.start_agent(project, model=model)
                results.append(f'{project.name}: deployed')
            elif action == 'stop':
                agent = Agent.get_by_project(pid)
                if agent and agent.status == 'running':
                    agent_runner.stop_agent(agent.id)
                    results.append(f'{project.name}: recalled')
                else:
                    results.append(f'{project.name}: not running')
        except Exception as e:
            results.append(f'{project.name}: {e}')

    flash(f'{", ".join(results)}. {get_quote("success")}', 'success')
    return redirect(url_for('main.launchpad'))


@projects_bp.route('/sync-roadmap/<project_id>', methods=['POST'])
def sync_roadmap(project_id):
    """Sync roadmap for a project."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    from max.services.roadmap import roadmap_service
    result = roadmap_service.sync_roadmap(project_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/analyze-logs/<project_id>', methods=['POST'])
def analyze_logs(project_id):
    """Run log analysis for a project."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    from max.services.log_analyzer import log_analyzer
    result = log_analyzer.analyze_project(project_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/learn/<project_id>', methods=['POST'])
def learn(project_id):
    """Run learning analysis — 86 learns from past mistakes."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    from max.services.learning import learning_service
    result = learning_service.analyze_and_propose(project_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('projects.detail', slug=project.slug))


@projects_bp.route('/sync-notion/<project_id>', methods=['POST'])
def sync_notion(project_id):
    """Sync Notion intelligence dossier."""
    project = Project.get_by_id(project_id)
    if not project:
        flash(get_quote('not_found'), 'error')
        return redirect(url_for('main.launchpad'))

    from max.services.notion_sync import notion_sync_service
    result = notion_sync_service.sync_project(project_id)
    flash(result['message'], 'success' if result['success'] else 'error')
    return redirect(url_for('projects.detail', slug=project.slug))


def _format_size(size_bytes):
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.0f} KB'
    else:
        return f'{size_bytes / (1024 * 1024):.1f} MB'


def _group_by_time(items, now):
    """Group items into time buckets."""
    from datetime import timedelta

    buckets = [
        ('This Week', now - timedelta(days=7)),
        ('This Month', now - timedelta(days=30)),
        ('This Year', now.replace(month=1, day=1)),
        ('Last Year', now.replace(year=now.year - 1, month=1, day=1)),
        ('2+ Years Ago', now.replace(year=now.year - 10, month=1, day=1)),
    ]

    groups = []
    remaining = list(items)

    for label, cutoff in buckets:
        group_items = [i for i in remaining if i['modified'] >= cutoff]
        remaining = [i for i in remaining if i['modified'] < cutoff]
        if group_items:
            groups.append({'label': label, 'entries': group_items})

    if remaining:
        groups.append({'label': 'Ancient History', 'entries': remaining})

    return groups
