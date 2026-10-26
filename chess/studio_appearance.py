"""Shared desktop visual system; preserves native widgets and board rendering."""
import tkinter as tk
from tkinter import ttk
import chess

PALETTES = {
    'light': dict(bg='#f4f5f1', surface='#fffefd', field='#f1f4ee', text='#23352d', muted='#68776f',
                  accent='#226247', on_accent='#ffffff', hover='#194b36', border='#dce3db',
                  stage='#e3e7df', selected='#e2eee4', focus='#a56a17'),
    'dark': dict(bg='#111c18', surface='#1b2a23', field='#142019', text='#edf4ea', muted='#adc0af',
                 accent='#99d8ad', on_accent='#142a1d', hover='#b3e6c1', border='#35493c',
                 stage='#14221b', selected='#294b36', focus='#e5c17b'),
}


class StudioAppearance:
    def _build_studio_header(self):
        header = tk.Frame(self.master)
        header._visual_role = 'header'
        header.grid(row=0, column=0, columnspan=2, sticky='ew', padx=20, pady=(16, 8))
        brand = tk.Frame(header)
        brand.pack(side='left', padx=16, pady=10)
        brand._visual_role = 'header'
        self.title_label = tk.Label(brand, text='Chess Studio', anchor='w')
        self.title_label.pack(anchor='w')
        self.header_caption = tk.Label(brand, text='A little practice. A better next move.', anchor='w')
        self.header_caption.pack(anchor='w', pady=(1, 0))
        self.theme_toggle = tk.Button(header, text='Dark mode', command=self._toggle_studio_theme)
        self.theme_toggle.pack(side='right', padx=(6, 14))
        self.header = header
        return header

    def _toggle_studio_theme(self):
        self.theme_var.set('light' if self.theme_var.get() == 'dark' else 'dark')

    def _build_player_cards(self, shell):
        self.player_cards = []
        for top in (True, False):
            frame = tk.Frame(shell, padx=12, pady=7)
            frame._visual_role = 'player'
            frame.pack(side='top' if top else 'bottom', fill='x', pady=(0, 8) if top else (8, 0))
            name = tk.Label(frame, anchor='w')
            name.pack(side='left')
            state = tk.Label(frame, anchor='e')
            state.pack(side='right')
            self.player_cards.append((frame, name, state))

    def _refresh_player_cards(self):
        if not hasattr(self, 'player_cards'):
            return
        palette = PALETTES.get(getattr(self, '_studio_theme', 'light'), PALETTES['light'])
        flipped = self.board_view.flipped
        colors = (chess.WHITE, chess.BLACK) if flipped else (chess.BLACK, chess.WHITE)
        activity = getattr(self, '_activity', 'game')
        outcome = getattr(self, '_player_cards_outcome', None)
        clocks = tuple(self.clock.get_time_string(color) for color in colors) if activity == 'game' and self.clock and self.clock_enabled else ()
        key = (self._studio_theme, self.text_scale, flipped, activity, self.play_mode,
               self._human_color(), self.board.turn, self.game_started, outcome is not None, clocks)
        if key == getattr(self, '_player_cards_render_key', None):
            return
        self._player_cards_render_key = key
        # Flipping/practice can recreate coordinate labels without a theme change.
        for child in self.board_view.parent.winfo_children():
            if child.winfo_class() == 'Label':
                child.configure(bg=palette['stage'], fg=palette['muted'], font=(self.ui_font, 9, 'bold'))
        for color, (frame, name, state) in zip(colors, self.player_cards):
            label = 'White' if color else 'Black'
            if activity != 'game':
                role = activity.title()
            elif self.play_mode == 'player_vs_ai':
                role = 'You' if color == self._human_color() else 'Computer'
            elif self.play_mode == 'ai_vs_ai':
                role = 'Computer'
            else:
                role = 'Local player'
            active = color == self.board.turn and outcome is None
            name.configure(text=f'{label}  /  {role}', font=(self.ui_font, round(10 * self.text_scale), 'bold'))
            if outcome is not None:
                status = 'Game over'
            else:
                status = 'To move' if active else 'Waiting'
                if activity == 'game' and not self.game_started and active:
                    status = 'Paused · to move'
            if activity == 'game' and self.clock and self.clock_enabled:
                status = self.clock.get_time_string(color) + '  ·  ' + status
            state.configure(text=status, fg=palette['accent'] if active else palette['muted'],
                            font=(self.ui_font, round(9 * self.text_scale), 'bold' if active else 'normal'))
            frame.configure(highlightthickness=1, highlightbackground=palette['accent'] if active else palette['border'])

    def _apply_studio_theme(self, theme):
        self._studio_theme = theme if theme in PALETTES else 'light'
        p = PALETTES[self._studio_theme]
        body = round(9 * self.text_scale)
        self.master.configure(bg=p['bg'])
        style = ttk.Style(self.master)
        style.theme_use('clam')
        style.configure('.', font=(self.ui_font, body), background=p['surface'], foreground=p['text'])
        style.configure('TNotebook', background=p['surface'], borderwidth=0, tabmargins=(0, 2, 0, 5),
                        bordercolor=p['border'], lightcolor=p['border'], darkcolor=p['border'])
        style.configure('TNotebook.Tab', padding=(9, 8), font=(self.ui_font, min(11, body)),
                        background=p['field'], foreground=p['muted'], borderwidth=0,
                        lightcolor=p['border'], darkcolor=p['border'], bordercolor=p['border'])
        style.map('TNotebook.Tab', background=[('selected', p['selected']), ('active', p['selected'])],
                  foreground=[('selected', p['accent']), ('active', p['text'])])
        style.configure('TCombobox', fieldbackground=p['field'], background=p['field'],
                        foreground=p['text'], arrowcolor=p['accent'], bordercolor=p['border'],
                        lightcolor=p['border'], darkcolor=p['border'], padding=5)
        style.map('TCombobox', fieldbackground=[('readonly', p['field']), ('disabled', p['surface'])],
                  foreground=[('disabled', p['muted']), ('readonly', p['text'])],
                  selectbackground=[('readonly', p['field'])], selectforeground=[('readonly', p['text'])])
        style.configure('Horizontal.TProgressbar', background=p['accent'], troughcolor=p['field'],
                        borderwidth=0, thickness=7)
        style.configure('Vertical.TScrollbar', background=p['border'], troughcolor=p['field'],
                        borderwidth=0, arrowcolor=p['muted'], width=10)
        self.master.option_add('*TCombobox*Listbox.background', p['field'])
        self.master.option_add('*TCombobox*Listbox.foreground', p['text'])
        self.master.option_add('*TCombobox*Listbox.selectBackground', p['selected'])
        self.master.option_add('*TCombobox*Listbox.selectForeground', p['text'])

        def decorate(widget, header=False):
            if widget is self.board_area:
                widget.configure(bg=p['stage'])
                self.board_view.parent.configure(bg=p['stage'])
                return
            header = header or getattr(widget, '_visual_role', '') == 'header'
            bg = '#172b24' if header else p['surface']
            fg = '#f4f8f1' if header else p['text']
            kind = widget.winfo_class()
            try:
                if kind in ('Frame', 'Labelframe', 'Toplevel'):
                    widget.configure(bg=bg, bd=0)
                    if kind == 'Labelframe':
                        widget.configure(fg=p['muted'], font=(self.ui_font, body, 'bold'), padx=8, pady=6,
                                         highlightthickness=1, highlightbackground=p['border'])
                elif kind == 'Label':
                    widget.configure(bg=bg, fg=fg, font=(self.ui_font, body))
                elif kind in ('Button', 'Menubutton'):
                    widget.configure(bg='#29483a' if header else p['field'], fg=fg,
                                     activebackground=p['accent'], activeforeground=p['on_accent'],
                                     relief='flat', bd=0, padx=9, pady=6, cursor='hand2',
                                     font=(self.ui_font, body), highlightthickness=1,
                                     highlightbackground=bg, highlightcolor=p['focus'])
                elif kind == 'Menu':
                    widget.configure(bg=p['surface'], fg=p['text'], activebackground=p['selected'],
                                     activeforeground=p['accent'], bd=0, relief='flat')
                elif kind in ('Checkbutton', 'Radiobutton'):
                    widget.configure(bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                                     selectcolor=p['field'], font=(self.ui_font, body),
                                     highlightthickness=1, highlightbackground=bg, highlightcolor=p['focus'])
                elif kind == 'TCombobox':
                    widget.configure(font=(self.ui_font, body))
                elif kind == 'Scale':
                    widget.configure(bg=bg, fg=fg, troughcolor=p['field'], bd=0, highlightthickness=0)
                elif kind in ('Entry', 'Listbox', 'Text'):
                    widget.configure(bg=p['field'], fg=p['text'], relief='flat', bd=0,
                                     highlightthickness=1, highlightbackground=p['border'], highlightcolor=p['focus'],
                                     selectbackground=p['accent'], selectforeground=p['on_accent'],
                                     font=(self.ui_font, body))
                    if kind != 'Listbox':
                        widget.configure(insertbackground=p['text'])
                    if kind == 'Entry':
                        widget.configure(disabledbackground=p['field'], disabledforeground=p['muted'])
                    if kind == 'Text':
                        widget.configure(padx=10, pady=8, spacing1=2, spacing3=3)
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                decorate(child, header)
        for child in self.master.winfo_children():
            decorate(child)
        self.board_shell.configure(bg=p['bg'])
        self.ctrl_frame.configure(bg=p['surface'], highlightthickness=1, highlightbackground=p['border'])
        self.title_label.configure(font=(self.ui_font, 22, 'bold'))
        self.header_caption.configure(fg='#bcd0c0', font=(self.ui_font, 9))
        self.theme_toggle.configure(text='Light mode' if self._studio_theme == 'dark' else 'Dark mode')
        self.status.configure(bg=p['bg'], fg=p['text'], font=(self.ui_font, 11, 'bold'))
        self.hints_label.configure(bg=p['bg'], fg=p['muted'])
        self.start_pause_button.configure(bg=p['accent'], fg=p['on_accent'], activebackground=p['hover'],
                                          activeforeground=p['on_accent'], font=(self.ui_font, body, 'bold'))
        if hasattr(self, 'white_clock_label'):
            for label in (self.white_clock_label, self.black_clock_label):
                label.configure(bg=p['field'], fg=p['text'], font=(self.ui_font, round(13 * self.text_scale), 'bold'))
        if hasattr(self, 'move_list_empty'):
            self.move_list_empty.configure(bg=p['field'], fg=p['muted'], font=(self.ui_font, body + 1))
        primary = [self.training_action_buttons.get('Start'), getattr(self, 'benchmark_start_button', None)] if hasattr(self, 'training_action_buttons') else []
        for button in primary:
            if button is not None:
                button.configure(bg=p['accent'], fg=p['on_accent'], activebackground=p['hover'],
                                 activeforeground=p['on_accent'], disabledforeground=p['on_accent'])
        self._player_cards_render_key = None
        self._refresh_player_cards()
