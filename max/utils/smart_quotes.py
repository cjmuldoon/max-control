"""Maxwell Smart quotes for the Max agent management platform.

"Would you believe... the most comprehensive CONTROL database ever assembled?"

Characters:
  - Maxwell Smart (Agent 86) — our main agent
  - Agent 99 — the competent one (VPS agent / secondary)
  - The Chief — the user
  - Siegfried — KAOS villain (production errors)
  - Hymie the Robot — the literal-minded agent
  - Larrabee — the bumbling assistant
  - Fang (Agent K-13) — the dog agent
"""
import random

# ===== Loading / Startup =====
LOADING = [
    "Would you believe... we're almost ready?",
    "Would you believe... CONTROL's fastest server?",
    "Would you believe... a highly trained team of agents?",
    "Would you believe... three interns and a mainframe?",
    "Would you believe... a quantum-encrypted satellite uplink?",
    "Would you believe... two cans and a really long string?",
    "The old 'loading screen' trick. Works every time.",
    "Activating the Cone of Silence...",
    "Contacting CONTROL headquarters...",
    "Agent 86 reporting for duty...",
    "Checking in with 99...",
    "Initializing CONTROL protocols...",
    "Polishing the shoe phone...",
    "Calibrating the sunroof of the Sunbeam Tiger...",
    "The Chief is expecting us...",
    "Running CONTROL security clearance check...",
    "Adjusting the Cone of Silence — can you hear me now?",
    "Hymie is computing the results...",
    "Would you believe... a carrier pigeon with a USB drive?",
]

# ===== Errors =====
ERRORS = [
    "Sorry about that, Chief.",
    "Missed it by that much!",
    "Would you believe... a minor setback?",
    "I asked you not to tell me that.",
    "That's the second biggest error I've ever seen.",
    "KAOS is behind this, I just know it.",
    "The old 'unexpected error' trick.",
    "Don't worry, I've got a plan. Well, half a plan.",
    "Siegfried must be interfering with our systems.",
    "Not the face! Not the face! ...I mean, not the server!",
    "If you had told me this would fail, I wouldn't have believed you.",
    "Would you believe... KAOS sabotage?",
    "Would you believe... a really unlucky solar flare?",
    "Of course, you realise this means we'll have to use Plan B.",
    "I think we need the Cone of Silence for this conversation.",
    "The old 'crash at the worst possible moment' trick.",
    "Larrabee must have touched something again.",
    "Even Fang could have seen that coming.",
]

# ===== Success =====
SUCCESS = [
    "And loving it!",
    "Another victory for CONTROL.",
    "Mission accomplished, Chief.",
    "Agent 86, reporting success.",
    "The old 'get it right the first time' trick.",
    "99 would be proud.",
    "CONTROL: 1, KAOS: 0.",
    "Would you believe... it worked on the first try?",
    "Take that, Siegfried!",
    "I knew it all along. Well, most of it. Some of it.",
    "The shoe phone is ringing with good news!",
    "That's what I call smart. Maxwell Smart.",
    "Even the Chief is smiling.",
    "CONTROL intelligence at its finest.",
    "Hymie, mark that down as a win.",
    "Would you believe... flawless execution?",
    "The Sunbeam Tiger of victories.",
]

# ===== Empty States =====
EMPTY_STATES = [
    "It's quiet... too quiet.",
    "No agents in the field. CONTROL is on standby.",
    "The shoe phone isn't ringing.",
    "Even KAOS takes a day off sometimes.",
    "All clear at CONTROL headquarters.",
    "Larrabee has nothing to report, as usual.",
    "Agent 99 is on vacation. No one's watching the desk.",
    "The Cone of Silence has nothing to silence.",
    "Hymie is standing perfectly still. As robots do.",
    "Would you believe... a perfectly empty dashboard?",
    "Fang is napping. No assignments today.",
    "CONTROL HQ is so quiet you could hear a micro-dot drop.",
]

# ===== Security / Cone of Silence =====
SECURITY = [
    "Activating the Cone of Silence.",
    "This information is classified, Chief.",
    "For your eyes only, Agent 86.",
    "CONTROL clearance level: Maximum.",
    "I could tell you, but then I'd have to transfer you to the Bermuda office.",
    "Engaging the Cone of Silence... can you hear me, Chief? CHIEF?!",
    "This is a secure CONTROL channel.",
    "Not even Siegfried can intercept this.",
    "Would you believe... military-grade encryption?",
    "Would you believe... a really strong padlock?",
    "Hymie, engage privacy protocols.",
]

# ===== Agent Starting =====
AGENT_START = [
    "Agent deployed to the field.",
    "86 is on the case!",
    "CONTROL has dispatched an agent.",
    "Would you believe... your finest operative?",
    "Max is on the move.",
    "The shoe phone is active.",
    "Agent 86, you have your assignment.",
    "Don't tell me, let me guess — another impossible mission?",
    "I'll take the case, Chief. When do I start? I already started? Good.",
    "99, cover me. I'm going in.",
    "This is a job for CONTROL's best. Well, CONTROL's most available.",
    "Activating field operations...",
    "Would you believe... an elite covert operative?",
    "Would you believe... a very motivated intern?",
]

# ===== Agent Stopping =====
AGENT_STOP = [
    "Agent recalled to headquarters.",
    "Mission complete. Agent standing down.",
    "86, return to CONTROL.",
    "The old 'strategic withdrawal' trick.",
    "Agent 86, your shift is over.",
    "Hanging up the shoe phone.",
    "Parking the Sunbeam Tiger.",
    "Deactivating field operations.",
    "Time to report back to the Chief.",
    "That's a wrap. 86 out.",
    "The Cone of Silence is being lowered.",
    "Even the best agents need a break.",
]

# ===== Terminal =====
TERMINAL = [
    "CONTROL Terminal — Classified Access",
    "You are now connected to the CONTROL mainframe.",
    "Agent 86's direct line. Speak clearly.",
    "Welcome to the shoe phone command line.",
    "Hymie's neural interface — speak slowly.",
    "CONTROL secure terminal. The Chief is watching.",
]

# ===== Notifications =====
NOTIFICATIONS = [
    "The shoe phone is ringing!",
    "Incoming transmission from the field!",
    "Chief, you have a message.",
    "CONTROL intelligence report incoming.",
    "Agent 86 has something to report.",
    "The old 'urgent notification' trick.",
    "Would you believe... breaking news from CONTROL?",
]

# ===== Bot / Comms =====
COMMS = [
    "CONTROL Communications Division online.",
    "Opening secure channel...",
    "The shoe phone network is active.",
    "Would you believe... a satellite uplink?",
    "Scrambling frequencies...",
    "Agent 99 is monitoring all channels.",
    "CONTROL to field agents — check in.",
    "The old 'encrypted message' trick.",
    "Even KAOS can't crack this channel.",
    "Larrabee, patch me through!",
]

# ===== Health Check =====
HEALTH_CHECK = [
    "CONTROL medical is running diagnostics.",
    "The old 'routine checkup' trick.",
    "Hymie is scanning all systems.",
    "Would you believe... a clean bill of health?",
    "Agent 86 is inspecting the premises.",
    "CONTROL security sweep in progress.",
    "99 is reviewing the intelligence reports.",
]

# ===== Scanning / Discovery =====
SCANNING = [
    "CONTROL intelligence gathering in progress...",
    "Agent 86 is surveilling the area.",
    "Would you believe... a state-of-the-art scanner?",
    "The old 'reconnaissance mission' trick.",
    "Checking for KAOS infiltrators...",
    "Hymie's sensors are fully operational.",
    "99 has eyes on the target.",
    "CONTROL satellite imagery coming in...",
]

# ===== Project Status Labels =====
STATUS_LABELS = {
    'running': '🟢 In the Field',
    'stopped': '⚪ At Headquarters',
    'error': '🔴 KAOS Interference',
    'no_agent': '📋 Awaiting Assignment',
    'active': '🟢 Active Operation',
    'inactive': '⚪ Standby',
    'paused': '🟡 Undercover',
}

# ===== Section Titles =====
SECTION_NAMES = {
    'launchpad': 'CONTROL Operations Centre',
    'terminal': 'CONTROL Mainframe Terminal',
    'tasks': 'Mission Briefings',
    'analytics': 'CONTROL Intelligence Division',
    'bots': 'CONTROL Communications',
    'settings': 'CONTROL Configuration',
    'projects': 'Field Operations',
    'agent_log': 'Field Report',
    'agent_control': 'Agent Deployment',
    'danger_zone': 'KAOS Territory',
    'health_check': 'CONTROL Medical',
    'schedule': 'Mission Schedule',
    'environments': 'Safe Houses',
    'backup': 'Emergency Protocols',
    'regression': 'Training Ground',
    'security': 'The Cone of Silence',
}

# ===== Tooltip / Placeholder Text =====
PLACEHOLDERS = {
    'project_name': 'e.g. Operation Sunbeam Tiger',
    'project_desc': 'Brief the Chief — what does this operation involve?',
    'github_url': 'CONTROL file reference (GitHub URL)',
    'notion_id': 'Intelligence dossier reference (Notion Page ID)',
    'bot_token': 'Classified — enter your bot token',
    'agent_message': 'Send orders to Agent 86...',
    'search': 'Search CONTROL database...',
    'terminal_input': 'Enter command, Agent...',
}

# ===== Page Titles =====
PAGE_TITLES = {
    'launchpad': 'Operations Centre',
    'new_project': 'Deploy New Field Agent',
    'project_detail': 'Operation Dossier',
    'terminal': 'CONTROL Mainframe',
    'tasks': 'Mission Briefings',
    'analytics': 'Intelligence Reports',
    'bots': 'Communications Division',
    'settings': 'CONTROL Configuration',
    'scan': 'Reconnaissance Results',
}

# ===== 404 / Not Found =====
NOT_FOUND = [
    "That agent doesn't exist. KAOS must have intercepted them.",
    "File not found. Siegfried probably shredded it.",
    "Would you believe... it was here a minute ago?",
    "The old 'disappearing document' trick.",
    "Larrabee must have misfiled it again.",
    "Even Hymie can't locate that resource.",
    "CONTROL has no record of that operation.",
]

# ===== Confirmation Dialogs =====
CONFIRM = [
    "Are you sure about that, Chief?",
    "The Chief wants confirmation — proceed?",
    "This is a one-way operation, Agent. Confirm?",
    "Would you believe... this action is irreversible?",
    "CONTROL protocol requires confirmation.",
    "99 says to double-check. Proceed?",
]


def get_quote(category='loading'):
    """Get a random Smart quote from the specified category."""
    categories = {
        'loading': LOADING,
        'error': ERRORS,
        'success': SUCCESS,
        'empty': EMPTY_STATES,
        'security': SECURITY,
        'agent_start': AGENT_START,
        'agent_stop': AGENT_STOP,
        'terminal': TERMINAL,
        'notification': NOTIFICATIONS,
        'comms': COMMS,
        'health_check': HEALTH_CHECK,
        'scanning': SCANNING,
        'not_found': NOT_FOUND,
        'confirm': CONFIRM,
    }
    quotes = categories.get(category, LOADING)
    return random.choice(quotes)


def get_status_label(status):
    """Get a Smart-themed status label."""
    return STATUS_LABELS.get(status, status)


def get_section_name(key):
    """Get a Smart-themed section name."""
    return SECTION_NAMES.get(key, key.replace('_', ' ').title())


def get_placeholder(key):
    """Get a Smart-themed placeholder."""
    return PLACEHOLDERS.get(key, '')


def get_page_title(key):
    """Get a Smart-themed page title."""
    return PAGE_TITLES.get(key, key.replace('_', ' ').title())
