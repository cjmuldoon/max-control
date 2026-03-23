#!/usr/bin/env python3
"""Max Menu Bar App — The Shoe Phone in your menu bar.

"Would you believe... a fully operational agent in your menu bar?"

Uses rumps to create a macOS menu bar app that provides quick access
to CONTROL headquarters and agent status.
"""
import rumps
import subprocess
import urllib.request
import json

MAX_URL = 'http://localhost:8086'


class MaxMenuBar(rumps.App):
    """CONTROL's menu bar presence — Agent 86 is always watching."""

    def __init__(self):
        super().__init__(
            '86',
            title='86',
            quit_button=None,  # We'll add our own
        )
        self.menu = [
            rumps.MenuItem('Open CONTROL HQ', callback=self.open_hq),
            None,  # Separator
            rumps.MenuItem('🟢 Operations Centre', callback=self.open_launchpad),
            rumps.MenuItem('💻 Mainframe Terminal', callback=self.open_terminal),
            rumps.MenuItem('📞 Shoe Phone (Bots)', callback=self.open_bots),
            rumps.MenuItem('⚙️ Configuration', callback=self.open_settings),
            None,  # Separator
            rumps.MenuItem('Agent Status', callback=None),
            None,  # Separator
            rumps.MenuItem('Quit Max — "86, signing off"', callback=self.quit_app),
        ]

    @rumps.clicked('Open CONTROL HQ')
    def open_hq(self, _):
        """Open Max in the default browser."""
        subprocess.Popen(['open', MAX_URL])

    def open_launchpad(self, _):
        subprocess.Popen(['open', f'{MAX_URL}/'])

    def open_terminal(self, _):
        subprocess.Popen(['open', f'{MAX_URL}/terminal/'])

    def open_bots(self, _):
        subprocess.Popen(['open', f'{MAX_URL}/bots/'])

    def open_settings(self, _):
        subprocess.Popen(['open', f'{MAX_URL}/settings/'])

    def quit_app(self, _):
        rumps.quit_application()

    @rumps.timer(30)
    def check_status(self, _):
        """Periodic status check — is CONTROL online?"""
        try:
            req = urllib.request.urlopen(f'{MAX_URL}/', timeout=3)
            if req.status == 200:
                self.title = '86'  # All good
            else:
                self.title = '86❌'
        except Exception:
            self.title = '86💤'  # Server not running


if __name__ == '__main__':
    MaxMenuBar().run()
