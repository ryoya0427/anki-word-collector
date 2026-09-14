"""Anki 단어 수집기. Python 3.10+, standard library only.

Run: py anki_word_collector.py
Translation: MyMemory GET API (selected language -> Korean), no API key.
"""
import html
import json
import os
from pathlib import Path
import queue
import re
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.parse
import urllib.request


def clean(value):
    return ' '.join(value.split())


class WordStore:
    def __init__(self, path):
        self.path = Path(path)
        self.snapshot = self.path.read_bytes() if self.path.exists() else None
        self.rows = []
        seen = set()
        if self.snapshot is not None:
            for number, line in enumerate(self.snapshot.decode('utf-8-sig').splitlines(), 1):
                if not line.strip():
                    continue
                fields = line.split('\t')
                if len(fields) != 2 or not all(clean(f) for f in fields):
                    raise ValueError(f'TSV {number}번째 줄은 단어와 뜻, 두 열이어야 합니다.')
                word, meaning = map(clean, fields)
                if word.casefold() in seen:
                    raise ValueError(f'TSV {number}번째 줄에 중복 단어가 있습니다: {word}')
                seen.add(word.casefold())
                self.rows.append((word, meaning))

    def find(self, word):
        return next((i for i, row in enumerate(self.rows)
                     if row[0].casefold() == clean(word).casefold()), None)

    def save(self, word, meaning, overwrite=False):
        word, meaning = clean(word), clean(meaning)
        if not word or not meaning:
            raise ValueError('영어 단어와 뜻을 모두 입력해 주세요.')
        current = self.path.read_bytes() if self.path.exists() else None
        if current != self.snapshot:
            raise RuntimeError('다른 프로그램에서 TSV가 변경되었습니다. 입력 내용을 복사한 뒤 앱을 다시 실행해 주세요.')
        rows = self.rows.copy()
        index = self.find(word)
        if index is not None:
            if not overwrite:
                raise FileExistsError(word)
            # Keep the original front field for Anki re-import matching.
            rows[index] = (rows[index][0], meaning)
        else:
            rows.append((word, meaning))
        data = ''.join(f'{w}\t{m}\n' for w, m in rows).encode('utf-8')
        name = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix='.tmp', delete=False) as f:
                name = f.name
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        self.snapshot = data
        self.rows = rows


LANGUAGE_CHOICES = {
    '자동 감지': None,
    '영어': 'en',
    '일본어': 'ja',
    '중국어': 'zh-CN',
    '스페인어': 'es',
    '프랑스어': 'fr',
    '독일어': 'de',
    '러시아어': 'ru',
    '아랍어': 'ar',
    '힌디어': 'hi',
}


def detect_source_language(text):
    """Detect scripts that have an unambiguous source language for this app."""
    if any('\u3040' <= char <= '\u30ff' for char in text):
        return 'ja'
    if any('\uac00' <= char <= '\ud7af' for char in text):
        return 'ko'
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        return 'zh-CN'
    if any('\u0400' <= char <= '\u052f' for char in text):
        return 'ru'
    if any('\u0600' <= char <= '\u06ff' for char in text):
        return 'ar'
    if any('\u0900' <= char <= '\u097f' for char in text):
        return 'hi'
    # Latin-script languages need the selector because script detection cannot
    # reliably distinguish English, Spanish, French, and German.
    return 'en'


def translate(word, source='en'):
    if len(word.encode('utf-8')) > 500:
        raise ValueError('자동 조회는 500바이트 이하만 가능합니다. 뜻을 직접 입력해 주세요.')
    if source == 'ko':
        return word
    query = urllib.parse.urlencode({'q': word, 'langpair': f'{source}|ko'})
    request = urllib.request.Request(
        'https://api.mymemory.translated.net/get?' + query,
        headers={'User-Agent': 'AnkiWordCollector/1.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read(1_000_000).decode('utf-8'))
    if str(result.get('responseStatus')) != '200' or result.get('quotaFinished'):
        raise RuntimeError(str(result.get('responseDetails') or '무료 사용량 제한 또는 번역 서비스 오류'))
    meaning = result.get('responseData', {}).get('translatedText')
    if not isinstance(meaning, str) or not meaning.strip():
        raise RuntimeError('번역 결과가 비어 있습니다.')
    return html.unescape(meaning).strip()


def expression_chunks(text):
    """Return useful learning units for a short English expression.

    This is intentionally conservative: a recognised infinitive + phrasal verb
    stays together ("to go around") and the remaining words are separate.
    Other multi-word input falls back to individual words, so a failed chunk
    never prevents the complete expression from being translated.
    """
    words = clean(text).split()
    if len(words) < 2:
        return []
    chunks = []
    index = 0
    particles = {'around', 'away', 'back', 'down', 'in', 'off', 'on', 'out', 'over', 'through', 'up'}
    while index < len(words):
        if (index + 2 < len(words) and words[index].casefold() == 'to'
                and words[index + 2].casefold().strip('.,!?;:') in particles):
            chunks.append(' '.join(words[index:index + 3]))
            index += 3
        else:
            chunks.append(words[index])
            index += 1
    return chunks


STUDY_HINTS = {
    'plenty to go around': (
        '모두에게 돌아갈 만큼 충분하다',
        [('plenty', '풍부함, 충분한 양'), ('to go around', '모두에게 돌아갈 만큼 있다')],
    ),
}


def translate_with_breakdown(text, translator=None, source='en'):
    """Translate the whole input, then show small phrase units for study."""
    hint = STUDY_HINTS.get(clean(text).casefold()) if source == 'en' and translator is None else None
    if hint is not None:
        whole, parts = hint
        return f'전체: {whole} | 표현 나누기: ' + '; '.join(
            f'{chunk} = {meaning}' for chunk, meaning in parts)
    translator = translator or (lambda value: translate(value, source))
    whole = translator(text)
    if source != 'en':
        return whole
    chunks = expression_chunks(text)
    if not chunks:
        return whole
    parts = []
    for chunk in chunks:
        try:
            parts.append(f'{chunk} = {translator(chunk)}')
        except Exception:
            # The complete translation remains usable even if a secondary lookup fails.
            continue
    if not parts:
        return f'전체: {whole}'
    return f'전체: {whole} | 표현 나누기: ' + '; '.join(parts)


class App:
    def __init__(self, root, path):
        self.root = root
        self.store = WordStore(path)
        self.messages = queue.Queue()
        self.generation = 0
        self.pending = False
        self.closed = False
        self.word = tk.StringVar()
        self.language_name = tk.StringVar(value='자동 감지')
        self.status = tk.StringVar(value='영어 입력 → Enter로 조회하면 뜻을 표시하고 자동 저장합니다.')
        self.count = tk.StringVar()
        self.topmost = tk.BooleanVar(value=False)
        root.title('Anki 단어 수집기')
        root.geometry('650x610')
        root.minsize(490, 440)
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(8, weight=1)
        title = ttk.Frame(frame)
        title.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(title, text='Anki 단어 수집기', font=('맑은 고딕', 16, 'bold')).pack(side='left')
        ttk.Checkbutton(title, text='항상 위', variable=self.topmost,
                        command=lambda: root.attributes('-topmost', self.topmost.get())).pack(side='right')
        input_header = ttk.Frame(frame)
        input_header.grid(row=1, column=0, sticky='ew')
        ttk.Label(input_header, text='단어 또는 표현').pack(side='left')
        ttk.Label(input_header, text='입력 언어:').pack(side='right', padx=(10, 4))
        self.language_box = ttk.Combobox(input_header, textvariable=self.language_name,
                                         values=list(LANGUAGE_CHOICES), state='readonly', width=12)
        self.language_box.pack(side='right')
        entry_frame = ttk.Frame(frame)
        entry_frame.grid(row=2, column=0, sticky='ew', pady=(5, 10))
        entry_frame.columnconfigure(0, weight=1)
        self.entry = ttk.Entry(entry_frame, textvariable=self.word, font=('맑은 고딕', 12))
        self.entry.grid(row=0, column=0, sticky='ew')
        self.lookup_button = ttk.Button(entry_frame, text='뜻 조회', command=self.lookup)
        self.lookup_button.grid(row=0, column=1, padx=(8, 0))
        ttk.Label(frame, text='한국어 뜻 · 표현은 전체 해석과 나눈 뜻을 표시 · 직접 수정 가능 (Shift+Enter: 줄바꿈)').grid(row=3, column=0, sticky='w')
        self.meaning = tk.Text(frame, height=5, wrap='word', font=('맑은 고딕', 11), undo=True)
        self.meaning.grid(row=4, column=0, sticky='ew', pady=5)
        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, sticky='ew', pady=7)
        ttk.Label(actions, text='조회 결과는 자동 저장 · 수동 뜻은 Enter로 저장').pack(side='left')
        ttk.Button(actions, text='새 단어', command=self.new_word).pack(side='left', padx=12)
        ttk.Label(actions, textvariable=self.count).pack(side='right')
        ttk.Label(frame, textvariable=self.status, wraplength=580).grid(row=6, column=0, sticky='w', pady=(0, 8))
        ttk.Label(frame, text='저장된 단어 · 두 번 클릭하면 불러오기').grid(row=7, column=0, sticky='w')
        table = ttk.Frame(frame)
        table.grid(row=8, column=0, sticky='nsew', pady=5)
        self.tree = ttk.Treeview(table, columns=('word', 'meaning'), show='headings', selectmode='browse')
        self.tree.heading('word', text='영어 단어')
        self.tree.heading('meaning', text='한국어 뜻')
        self.tree.column('word', width=155, minwidth=100)
        self.tree.column('meaning', width=370, minwidth=180)
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        ttk.Label(frame, text='번역: MyMemory 무료 API · 입력한 단어·표현을 외부 서비스로 전송',
                  wraplength=580).grid(row=9, column=0, sticky='w', pady=(8, 3))
        ttk.Label(frame, text=f'저장 파일: {path}', wraplength=580).grid(row=10, column=0, sticky='w')
        self.entry.bind('<Return>', self.enter_word)
        self.meaning.bind('<Return>', self.enter_meaning)
        self.meaning.bind('<Shift-Return>', self.newline)
        self.tree.bind('<Double-1>', self.load_selected)
        self.word.trace_add('write', self.word_changed)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()
        self.entry.focus_set()
        self.poll_id = root.after(100, self.poll)

    def invalidate(self):
        self.generation += 1
        self.pending = False
        self.lookup_button.configure(state='normal')

    def word_changed(self, *_):
        self.invalidate()
        self.meaning.delete('1.0', 'end')
        self.status.set('Enter로 뜻 조회 · 표현은 전체와 구성 단위 뜻을 함께 표시합니다.')

    def text(self):
        return self.meaning.get('1.0', 'end-1c').strip()

    def source_language(self, text):
        selected = LANGUAGE_CHOICES[self.language_name.get()]
        return selected or detect_source_language(text)

    def enter_word(self, event=None):
        if self.text():
            self.save()
        elif not self.pending:
            self.lookup()
        return 'break'

    def enter_meaning(self, event=None):
        self.save()
        return 'break'

    def newline(self, event=None):
        self.meaning.insert('insert', '\n')
        return 'break'

    def lookup(self):
        word = clean(self.word.get())
        if not word or self.pending:
            return
        if self.text() and not messagebox.askyesno('뜻 다시 조회', '입력한 뜻을 새 조회 결과로 바꿀까요?', parent=self.root):
            return
        self.invalidate()
        token = self.generation
        original = self.text()
        source = self.source_language(word)
        self.pending = True
        self.lookup_button.configure(state='disabled')
        self.status.set(f'MyMemory 조회 중… 입력 언어: {source} · 기다리는 동안 뜻을 직접 입력하고 저장할 수도 있습니다.')
        def worker():
            try:
                self.messages.put((token, original, translate_with_breakdown(word, source=source), None))
            except Exception as error:
                self.messages.put((token, original, None, str(error)))
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(15000, lambda: self.timeout(token))

    def timeout(self, token):
        if not self.closed and token == self.generation and self.pending:
            self.invalidate()
            self.status.set('조회 시간이 초과되었습니다. 뜻을 직접 입력해 저장하거나 다시 조회해 주세요.')
            self.meaning.focus_set()

    def poll(self):
        while True:
            try:
                token, original, meaning, error = self.messages.get_nowait()
            except queue.Empty:
                break
            if token != self.generation:
                continue
            self.invalidate()
            if error:
                self.status.set(f'조회 실패: {error[:140]} · 뜻을 직접 입력해 저장하세요.')
            elif self.text() != original:
                self.status.set('직접 입력한 뜻을 유지했습니다. Enter로 저장하세요.')
            else:
                self.meaning.delete('1.0', 'end')
                self.meaning.insert('1.0', meaning)
                if self.save_lookup_result(self.word.get(), meaning):
                    continue
            self.meaning.focus_set()
        self.poll_id = self.root.after(100, self.poll)

    def save(self):
        word, meaning = clean(self.word.get()), self.text()
        if not word or not meaning:
            self.status.set('영어 단어와 뜻을 모두 입력해 주세요.')
            return
        index = self.store.find(word)
        overwrite = False
        if index is not None:
            old_word, old_meaning = self.store.rows[index]
            overwrite = messagebox.askyesno('중복 단어',
                f'이미 저장된 단어: {old_word}\n기존 뜻: {old_meaning}\n\n새 뜻: {meaning}\n\n기존 뜻을 덮어쓸까요?', parent=self.root)
            if not overwrite:
                self.status.set('저장을 취소했습니다. 기존 항목은 그대로 유지됩니다.')
                return
        try:
            self.store.save(word, meaning, overwrite)
        except Exception as error:
            messagebox.showerror('저장 실패', f'{error}\n\n입력 내용은 유지됩니다.', parent=self.root)
            return
        self.word.set('')
        self.refresh()
        self.entry.focus_set()
        self.status.set(f'“{word}” 저장 완료 · 다음 단어를 입력하세요.')

    def save_lookup_result(self, word, meaning):
        """Save a successful lookup without silently replacing existing data."""
        if self.store.find(word) is not None:
            self.status.set(f'“{word}”은(는) 이미 저장되어 있어 기존 뜻을 유지했습니다.')
            return False
        try:
            self.store.save(word, meaning)
        except Exception as error:
            messagebox.showerror('자동 저장 실패',
                f'{error}\n\n화면의 뜻은 유지됩니다. 수정 후 Enter를 눌러 수동 저장해 주세요.',
                parent=self.root)
            return False
        self.refresh()
        self.status.set(f'“{word}” 조회·자동 저장 완료 · 다음 단어를 바로 입력하세요.')
        self.entry.focus_set()
        self.entry.selection_range(0, 'end')
        return True

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.store.rows):
            self.tree.insert('', 'end', iid=str(index), values=row)
        self.count.set(f'저장된 단어: {len(self.store.rows)}개')
        if self.store.rows:
            self.tree.see(str(len(self.store.rows) - 1))

    def load_selected(self, event=None):
        selected = self.tree.selection()
        if not selected or not self.discard_ok():
            return
        word, meaning = self.store.rows[int(selected[0])]
        self.word.set(word)
        self.meaning.insert('1.0', meaning)
        self.meaning.focus_set()
        self.status.set('저장된 항목을 불러왔습니다. 수정 후 저장하면 덮어쓰기 여부를 확인합니다.')

    def discard_ok(self):
        return not (self.word.get().strip() or self.text()) or messagebox.askyesno(
            '입력 내용 확인', '현재 입력 내용은 아직 저장하지 않았습니다. 계속할까요?', parent=self.root)

    def new_word(self):
        if self.discard_ok():
            self.word.set('')
            self.entry.focus_set()

    def close(self):
        if self.discard_ok():
            self.closed = True
            self.root.after_cancel(self.poll_id)
            self.root.destroy()


def main():
    root = tk.Tk()
    root.withdraw()
    path = Path(__file__).resolve().with_name('anki_words.tsv')
    # Lock the application for this folder on Windows; avoids two writers.
    lock = None
    try:
        if os.name == 'nt':
            import msvcrt
            lock = open(path.with_suffix('.lock'), 'a+b')
            if lock.seek(0, 2) == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError('이 폴더의 단어 수집기가 이미 실행 중입니다.')
        App(root, path)
    except Exception as error:
        messagebox.showerror('시작 실패', f'{error}\n\n기존 TSV는 변경하지 않았습니다. 파일과 폴더 권한을 확인해 주세요.', parent=root)
        root.destroy()
        if lock:
            lock.close()
        return
    root.deiconify()
    try:
        root.mainloop()
    finally:
        if lock:
            lock.close()


if __name__ == '__main__':
    main()
