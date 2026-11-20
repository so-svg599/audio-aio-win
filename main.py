# Crash diagnostics are initialized before any third-party/Qt import so even
# a failed PySide6 DLL load is recorded in windowed (no-console) builds.
import os, sys, json, sqlite3, uuid, time, random, traceback, faulthandler
from pathlib import Path

def _crash_log_paths():
    candidates = []
    try:
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "crash.log")
        else:
            candidates.append(Path(__file__).resolve().parent / "crash.log")
    except Exception:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "AudioPlayerAIO" / "crash.log")
    else:
        candidates.append(Path.home() / "AudioPlayerAIO" / "crash.log")
    return candidates

_CRASH_HANDLES = []
def _write_crash(text):
    written = False
    for path in _crash_log_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as log:
                log.write("\n" + "=" * 72 + "\n" + text + "\n")
                log.flush()
            written = True
        except Exception:
            continue
    return written

def _show_crash_message(text):
    # ctypes/user32 is intentionally independent of Qt, which may have failed to load.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,
                "AudioPlayerAIO a rencontré une erreur au démarrage.\n"
                "Le détail est enregistré dans crash.log et dans %APPDATA%\\AudioPlayerAIO.\n\n"
                + text[-3000:], "AudioPlayerAIO — erreur", 0x10)
        except Exception:
            pass

def _report_uncaught(exc_type, exc_value, exc_tb):
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _write_crash(detail)
    _show_crash_message(detail)

try:
    sys.excepthook = _report_uncaught
    for _path in _crash_log_paths():
        try:
            _path.parent.mkdir(parents=True, exist_ok=True)
            _handle = _path.open("a", encoding="utf-8")
            _CRASH_HANDLES.append(_handle)
        except Exception:
            continue
    if _CRASH_HANDLES:
        faulthandler.enable(file=_CRASH_HANDLES[0], all_threads=True)
except Exception:
    pass

from urllib.parse import urlparse
from PySide6.QtCore import Qt, QUrl, QObject, Signal, QRunnable, QThreadPool, QEvent, QSize, QTimer, QPointF
from PySide6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QPen, QPolygonF
from PySide6.QtWidgets import *
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import requests
try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None

APP = 'AudioPlayerAIO'
DATA = Path(os.getenv('APPDATA', str(Path.home()))) / APP
DATA.mkdir(parents=True, exist_ok=True)
DB, CFG = DATA / 'library.sqlite3', DATA / 'settings.json'
EXTS = {'.mp3', '.flac', '.m4a', '.aac', '.ogg', '.opus', '.wav', '.wma', '.alac'}
DEFAULTS = {'theme':'Windows Vista/7 Aero', 'accent_color':'Bleu', 'visible_sources':['Local','pCloud','YouTube Music','SoundCloud','WebDAV','SMB','FTP'], 'show_artwork':True, 'high_audio_quality':True, 'skip_silence':False, 'playback_speed':1.0, 'playback_pitch':1.0, 'remember_playback_parameters':False, 'remote_profiles':[], 'youtube_cookie':'', 'youtube_browser':'', 'soundcloud_cookie':'', 'soundcloud_browser':'', 'soundcloud_username':'', 'youtube_handle':'', 'soundcloud_history':[], 'dark_mode':False, 'pcloud_region':'US', 'pcloud_username':'', 'pcloud_password':'', 'pcloud_token':'', 'tray_enabled':False, 'volume':70, 'repeat':'Off', 'shuffle':False, 'library_folders':[], 'last_error':''}
ACCENTS = {'Bleu':'#0078d4','Vert':'#27864a','Violet':'#805ad5','Rouge':'#c62828','Orange':'#d97706','Rose':'#d9468f'}
THEMES = {
 'Windows Vista/7 Aero': "QMainWindow,QWidget{background:#dceaf8;color:#132942;font-family:'Segoe UI';} QFrame#card,QTableWidget,QListWidget{background:#f3f8fd;border:1px solid #a9c7e4;border-radius:8px;} QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fff,stop:1 #b8d9f7);border:1px solid #7aa9d1;border-radius:6px;padding:7px 12px;color:#163958;} QPushButton:hover{background:#d9edff;} QPushButton:checked{background:#8fc4ef;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #a8c5df;border-radius:5px;padding:6px;} QHeaderView::section{background:#d4e7f7;padding:7px;border:0;} QSlider::groove:horizontal{height:6px;background:#b4cde3;border-radius:3px;} QSlider::handle:horizontal{background:#157ac0;width:13px;margin:-4px 0;border-radius:6px;}",
 'Windows 10/11 Metro/Fluent': "QMainWindow,QWidget{background:#f4f4f4;color:#202020;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:white;border:1px solid #dedede;border-radius:4px;} QPushButton{background:#e9e9e9;border:0;border-radius:3px;padding:8px 12px;color:#222;} QPushButton:hover{background:#d8eaf8;} QPushButton:checked{background:#c8e4f8;color:#0067b8;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #c8c8c8;border-radius:3px;padding:6px;} QHeaderView::section{background:#f1f1f1;padding:7px;border:0;}",
 'Sombre': "QMainWindow,QWidget{background:#17191d;color:#e7e9ee;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:#22252b;border:1px solid #363a43;border-radius:8px;} QPushButton{background:#30343c;border:1px solid #414650;border-radius:6px;padding:8px 12px;color:#eee;} QPushButton:hover{background:#414955;} QPushButton:checked{background:#28577c;} QLineEdit,QComboBox,QPlainTextEdit{background:#22252b;border:1px solid #414650;border-radius:5px;padding:6px;color:#eee;} QHeaderView::section{background:#30343c;padding:7px;border:0;}",
 'Clair': "QMainWindow,QWidget{background:#faf9f6;color:#333;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:#fff;border:1px solid #e6e0d7;border-radius:8px;} QPushButton{background:#f1eee8;border:1px solid #e0d9cf;border-radius:6px;padding:8px 12px;color:#333;} QPushButton:hover{background:#e7dfd2;} QPushButton:checked{background:#d7e9da;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #d9d2c8;border-radius:5px;padding:6px;} QHeaderView::section{background:#f1eee8;padding:7px;border:0;}",
 'Windows Media Player 7/8': "QMainWindow,QWidget{background:#c8cdd3;color:#18212b;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:#f1f3f5;border:1px solid #87929e;border-radius:3px;} QPushButton{background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fff,stop:1 #bdc5cd);border:1px solid #7c8996;border-radius:4px;padding:6px 10px;color:#192632;} QPushButton:hover{background:#e2ebf5;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #8f9aa6;padding:5px;}",
 'Windows Media Player 9/10 XP Luna': "QMainWindow,QWidget{background:#dce8f6;color:#102d53;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:#f6f9fd;border:1px solid #89a9d0;border-radius:8px;} QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fff,stop:1 #a9c9ef);border:1px solid #527caf;border-radius:12px;padding:7px 12px;color:#153765;} QPushButton:hover{background:#c5ddfa;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #94aed0;border-radius:5px;padding:6px;}",
 'Windows Media Player 11 Vista': "QMainWindow,QWidget{background:#d3dce3;color:#162735;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:#f5f8fa;border:1px solid #9aaab5;border-radius:5px;} QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fff,stop:1 #b8c9d4);border:1px solid #8499a7;border-radius:8px;padding:7px 11px;color:#17364d;} QPushButton:hover{background:#d8eaf4;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #9cabb5;border-radius:4px;padding:6px;}",
 'Windows Media Player 12 Windows 10': "QMainWindow,QWidget{background:#f2f3f5;color:#202124;font-family:'Segoe UI';} QFrame#card,QTableWidget{background:white;border:1px solid #d9dce1;border-radius:2px;} QPushButton{background:#e8eaed;border:0;border-radius:3px;padding:8px 12px;color:#24262a;} QPushButton:hover{background:#dce8f5;} QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #c8ccd1;border-radius:2px;padding:6px;}"
}

def readcfg():
    try: raw=json.loads(CFG.read_text('utf-8'))
    except Exception: raw={}
    raw={k:v for k,v in raw.items() if k in DEFAULTS}
    return {**DEFAULTS, **raw}
def writecfg(c): CFG.write_text(json.dumps(c, ensure_ascii=False, indent=2), 'utf-8')
def dbinit():
    with sqlite3.connect(DB) as d:
        d.execute('''CREATE TABLE IF NOT EXISTS tracks(id TEXT PRIMARY KEY,path TEXT UNIQUE,title TEXT,artist TEXT,album TEXT,genre TEXT,year TEXT,duration REAL,art BLOB,favorite INTEGER DEFAULT 0,added REAL)''')
        d.execute('CREATE TABLE IF NOT EXISTS playlists(name TEXT PRIMARY KEY)')
        d.execute('CREATE TABLE IF NOT EXISTS playlist_tracks(name TEXT,path TEXT,position INTEGER,PRIMARY KEY(name,path))')
        d.execute('CREATE TABLE IF NOT EXISTS recent(path TEXT PRIMARY KEY,played REAL)')
        cols={r[1] for r in d.execute('PRAGMA table_info(tracks)')}
        if 'year' not in cols: d.execute("ALTER TABLE tracks ADD COLUMN year TEXT DEFAULT ''")
        if 'favorite' not in cols: d.execute('ALTER TABLE tracks ADD COLUMN favorite INTEGER DEFAULT 0')
        if 'added' not in cols: d.execute('ALTER TABLE tracks ADD COLUMN added REAL DEFAULT 0')
def readtag(tags, keys, default=''):
    for key in keys:
        try:
            v=tags.get(key)
            if v:
                if hasattr(v,'text'): v=v.text[0]
                elif isinstance(v,list): v=v[0]
                return str(v).strip()
        except Exception: pass
    return default
def metadata(path):
    p=Path(path); r={'title':p.stem,'artist':'Inconnu','album':'Inconnu','genre':'','year':'','duration':0,'art':None}
    if MutagenFile:
        try:
            m=MutagenFile(str(p))
            if m:
                r['duration']=float(getattr(m.info,'length',0) or 0); tags=m.tags or {}
                r['title']=readtag(tags,['title','TIT2'],r['title']);r['artist']=readtag(tags,['artist','TPE1'],r['artist']);r['album']=readtag(tags,['album','TALB'],r['album']);r['genre']=readtag(tags,['genre','TCON'],'');r['year']=readtag(tags,['date','year','TDRC','TYER'],'')[:4]
                pics=getattr(m,'pictures',None)
                if pics:r['art']=pics[0].data
                elif tags:
                    for k in ('APIC:','covr'):
                        if tags.get(k):
                            item=tags[k][0] if isinstance(tags[k],list) else tags[k];r['art']=item.data if hasattr(item,'data') else bytes(item);break
        except Exception: pass
    return r
class PCloud2FARequired(Exception):
    def __init__(self, token):
        self.token=token
        super().__init__('Une vérification pCloud à deux facteurs est requise.')

class Signals(QObject):
    done=Signal(object); error=Signal(str)
class Job(QRunnable):
    def __init__(self, fn, *args): super().__init__();self.fn=fn;self.args=args;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.fn(*self.args))
        except PCloud2FARequired as e:self.signals.done.emit({'pcloud_2fa_required':True,'token':e.token})
        except Exception as e:self.signals.error.emit(str(e))
def ytdlp_options(cookie='', browser=''):
    opts={'quiet':True,'no_warnings':True,'extract_flat':'in_playlist','skip_download':True}
    if cookie and Path(cookie).is_file(): opts['cookiefile']=cookie
    if browser: opts['cookiesfrombrowser']=(browser,)
    return opts

def ytdlp_entries(data, service):
    result=[]
    for e in data.get('entries') or []:
        if not e: continue
        url=e.get('webpage_url') or e.get('original_url') or e.get('url')
        ident=e.get('id')
        if service=='SoundCloud' and str(url or '').startswith('https://api.soundcloud.com/') and e.get('webpage_url'):
            url=e.get('webpage_url')
        if url and not str(url).startswith(('http://','https://')):
            if service=='YouTube Music': url='https://www.youtube.com/watch?v='+str(ident or url)
            elif service=='SoundCloud': url='https://soundcloud.com/'+str(url).lstrip('/')
        result.append({'title':e.get('title') or 'Sans titre','artist':e.get('uploader') or e.get('channel') or e.get('creator') or service,'album':service,'duration':e.get('duration') or 0,'remote':True,'service':service,'webpage_url':url,'id':ident})
    return result

def ytdlp_search(query, service, cookie='', browser=''):
    try: import yt_dlp
    except ImportError: raise RuntimeError('yt-dlp manquant : pip install -r requirements.txt')
    prefix='ytsearch' if service=='YouTube Music' else 'scsearch'
    opts=ytdlp_options(cookie,browser); opts['noplaylist']=True
    with yt_dlp.YoutubeDL(opts) as ydl:data=ydl.extract_info(f'{prefix}10:{query}',download=False)
    return ytdlp_entries(data,service)

def soundcloud_permalink(value):
    value=(value or '').strip()
    if not value:return ''
    if '://' not in value and value.lower().startswith(('soundcloud.com/','www.soundcloud.com/','m.soundcloud.com/')):
        value='https://'+value
    if '://' in value:
        parsed=urlparse(value)
        if parsed.netloc.lower()=='soundcloud.com' or parsed.netloc.lower().endswith('.soundcloud.com'):
            parts=[x for x in parsed.path.split('/') if x]
            if parts and parts[0].lower() not in ('you','discover','search','terms-of-use','pages'):
                return parts[0].lstrip('@')
        return ''
    return value.lstrip('@').strip().strip('/')

def ytdlp_browse(service, section, cookie='', browser='', username='', youtube_handle='', soundcloud_history=None):
    try: import yt_dlp
    except ImportError: raise RuntimeError('yt-dlp manquant : pip install -r requirements.txt')
    if service=='SoundCloud' and section=='Historique':
        entries=[]
        for item in soundcloud_history or []:
            if item.get('webpage_url'):
                entries.append({**item,'remote':True,'service':'SoundCloud'})
        return {'browse_entries':entries,'notice':'Historique local SoundCloud : titres SoundCloud lus sur cet appareil.'}
    if service=='YouTube Music':
        handle=(youtube_handle or '').strip()
        if '://' in handle:
            parsed=urlparse(handle);handle=parsed.path.strip('/')
            if handle.endswith('/videos'): upload='https://www.youtube.com/'+handle
            else: upload='https://www.youtube.com/'+handle+'/videos' if handle else 'https://www.youtube.com/feed/you'
        elif handle.startswith('@'): upload=f'https://www.youtube.com/{handle}/videos'
        elif handle.startswith('channel/') or handle.startswith('c/') or handle.startswith('user/'):
            upload=f'https://www.youtube.com/{handle.rstrip("/")}/videos'
        elif handle: upload=f'https://www.youtube.com/@{handle}/videos'
        else: upload='https://www.youtube.com/feed/you'
        playlists=f'https://www.youtube.com/{handle}/playlists' if handle else 'https://www.youtube.com/feed/recommended'
        choices={
          'Accueil':[':ytrec','https://www.youtube.com/feed/recommended'],
          'Playlists':['https://www.youtube.com/feed/playlists',playlists],
          'Uploads':[upload,'https://www.youtube.com/feed/you'],
          'Historique':[':ythistory','https://www.youtube.com/feed/history'],
          'Aimé':['https://music.youtube.com/playlist?list=LM','https://www.youtube.com/playlist?list=LL']}
    else:
        user=soundcloud_permalink(username)
        if section!='Accueil' and not user:
            raise RuntimeError(f"Configurez votre nom ou URL de profil SoundCloud dans Paramètres pour charger « {section} ». L’historique est local à l’application.")
        choices={
          'Accueil':[f'https://soundcloud.com/{user}/reposts','scsearch10:trending music'] if user else ['scsearch10:trending music'],
          'Playlists':[f'https://soundcloud.com/{user}/sets','scsearch10:playlists music'],
          'Uploads':[f'https://soundcloud.com/{user}/tracks','scsearch10:trending music'],
          'Aimé':[f'https://soundcloud.com/{user}/likes','scsearch10:popular music']}
    opts=ytdlp_options(cookie,browser); opts['noplaylist']=False
    attempts=choices.get(section)
    if not attempts:raise RuntimeError(f'Onglet {section!r} non pris en charge pour {service}.')
    errors=[]
    for index,url in enumerate(attempts):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:data=ydl.extract_info(url,download=False)
            result=ytdlp_entries(data,service)
            if not result and index+1<len(attempts):
                errors.append(f'{url}: aucun élément retourné');continue
            note=''
            if index:
                note=f"L’URL principale de l’onglet « {section} » a échoué; affichage du repli pris en charge ({url})."
            elif service=='SoundCloud' and section=='Accueil' and not username:
                note='Accueil SoundCloud : résultats de recherche « tendances » (yt-dlp ne fournit pas le flux d’accueil sans profil).'
            return {'browse_entries':result,'notice':note}
        except Exception as e:errors.append(f'{url}: {e}')
    raise RuntimeError(f"Impossible de charger {section} ({service}). Essais effectués : "+' | '.join(errors))

def ytdlp_stream(item, cookie='', browser=''):
    import yt_dlp
    url=item.get('webpage_url')
    if not url: raise RuntimeError('URL de lecture absente pour cet élément.')
    opts=ytdlp_options(cookie,browser); opts.update({'format':'bestaudio/best','noplaylist':True,'extract_flat':False})
    with yt_dlp.YoutubeDL(opts) as ydl:info=ydl.extract_info(url,download=False)
    return {'url':info.get('url'),'title':info.get('title') or item['title'],'artist':info.get('uploader') or item['artist']}
class SeekSlider(QSlider):
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:
            value=QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),event.position().toPoint().x(),max(1,self.width()))
            self.setSliderDown(True);self.setValue(value);self.sliderMoved.emit(value);event.accept();return
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.LeftButton:
            value=QStyle.sliderValueFromPosition(self.minimum(),self.maximum(),event.position().toPoint().x(),max(1,self.width()))
            self.setValue(value);self.sliderMoved.emit(value);self.setSliderDown(False);event.accept();return
        super().mouseReleaseEvent(event)

class MediaControlButton(QPushButton):
    """Qt-painted transport glyph, independent of platform emoji fonts."""
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setAccessibleName({'previous':'Précédent','next':'Suivant','play':'Lecture / Pause','stop':'Arrêter'}[kind])
        self.setToolTip(self.accessibleName())
        self.setFixedSize(40, 36)
        if kind == 'play': self.setFixedSize(48, 42)

    def paintEvent(self, event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        r=self.rect().adjusted(2,2,-2,-2)
        if self.kind=='play':
            grad=QLinearGradient(r.topLeft(),r.bottomLeft());grad.setColorAt(0,QColor('#ffffff'));grad.setColorAt(.32,QColor('#67bdff'));grad.setColorAt(1,QColor('#075aab'))
            p.setBrush(grad);p.setPen(QPen(QColor('#d5eeff'),2));p.drawEllipse(r)
            p.setBrush(QColor('white'));p.setPen(Qt.NoPen)
            if self.text()=='⏸':
                p.drawRoundedRect(int(r.center().x()-6),int(r.center().y()-8),4,16,1,1);p.drawRoundedRect(int(r.center().x()+2),int(r.center().y()-8),4,16,1,1)
            else:
                pts=[(r.center().x()-5,r.center().y()-9),(r.center().x()-5,r.center().y()+9),(r.center().x()+10,r.center().y())]
                p.drawPolygon(QPolygonF([QPointF(x,y) for x,y in pts]))
            return
        p.setPen(Qt.NoPen);p.setBrush(self.palette().button());p.drawRoundedRect(r,5,5)
        p.setBrush(self.palette().buttonText());cx=r.center().x();cy=r.center().y()
        if self.kind=='stop':p.drawRect(int(cx-6),int(cy-6),12,12)
        else:
            forward=self.kind=='next';direction=1 if forward else -1
            x=int(cx+direction*3);p.drawPolygon(QPolygonF([QPointF(x-direction*6,cy-8),QPointF(x-direction*6,cy+8),QPointF(x+direction*6,cy)]))
            p.drawRect(int(cx-direction*10-1),int(cy-8),2,16)

class NowPlayingVisualizer(QWidget):
    """Compact animated spectrum-style decoration for the Now Playing panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0
        self.setMinimumHeight(74)
        self.setMaximumHeight(110)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance)
        self.timer.start(90)

    def advance(self):
        self.phase = (self.phase + 1) % 1000
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor('#111c2b'))
        w, h = self.width(), self.height()
        count = max(12, min(38, w // 12))
        gap = 4
        barw = max(3, (w - (count + 1) * gap) // count)
        for i in range(count):
            wave = (i * 0.63 + self.phase * 0.075)
            height = 9 + (0.5 + 0.5 * __import__('math').sin(wave)) * (h * 0.72)
            x = gap + i * (barw + gap)
            y = h - height - 5
            grad = QLinearGradient(x, y, x, h)
            grad.setColorAt(0, QColor('#74d7ff'))
            grad.setColorAt(1, QColor('#1377cf'))
            painter.setPen(Qt.NoPen)
            painter.setBrush(grad)
            painter.drawRoundedRect(int(x), int(y), int(barw), int(height), 2, 2)

class PlayerWindow(QMainWindow):
    def __init__(self):
        super().__init__();self.cfg=readcfg();dbinit();self.page='Bibliothèque';self.group='Titres';self.rows=[];self.current=-1;self.current_item=None;self.dragging=False;self.jobs=[];self.pool=QThreadPool.globalInstance();self.tray=None;self.active_playlist=None;self.service_section={'YouTube Music':'Accueil','SoundCloud':'Accueil'}
        self.setWindowTitle(APP);self.resize(1280,820);self.player=QMediaPlayer(self);self.audio=QAudioOutput(self);self.player.setAudioOutput(self.audio);self.audio.setVolume(self.cfg['volume']/100)
        self.player.positionChanged.connect(self.position);self.player.durationChanged.connect(self.duration);self.player.playbackStateChanged.connect(self.playstate);self.player.mediaStatusChanged.connect(self.media_status);self.player.errorOccurred.connect(self.player_error);self.player.seekableChanged.connect(self.seekability_changed)
        self.build();self.apply_theme(self.cfg['theme']);self.refresh();self.setup_tray(self.cfg['tray_enabled'])
    def build(self):
        self.root=QWidget();self.setCentralWidget(self.root)
        self.nav_panel=QFrame();self.nav_panel.setObjectName('card');self.nav_panel.setFixedWidth(195)
        navlay=QVBoxLayout(self.nav_panel);navlay.addWidget(QLabel('EXPLORER'));self.nav=[]
        for name,label in [('Accueil','Accueil'),('Bibliothèque','Bibliothèque'),('Musique locale','Musique locale'),('Playlists','Playlists'),('Favoris','Favoris'),('Lectures récentes','Lectures récentes'),('YouTube Music','YouTube'),('SoundCloud','SoundCloud'),('pCloud','pCloud'),('WebDAV','WebDAV'),('SMB','SMB'),('FTP','FTP')]:
            b=QPushButton(label);b.setCheckable(True);b.clicked.connect(lambda checked=False,n=name:self.navigate(n));navlay.addWidget(b);self.nav.append((name,b))
        navlay.addStretch();add=QPushButton('＋ Ajouter des dossiers');add.clicked.connect(self.add_folders);navlay.addWidget(add)
        self.header_widget=QWidget();header=QHBoxLayout(self.header_widget);header.setContentsMargins(0,0,0,0)
        self.brand=QLabel('♫  AudioPlayerAIO');self.brand.setStyleSheet('font-size:21px;font-weight:700');header.addWidget(self.brand);header.addStretch()
        self.search=QLineEdit();self.search.setPlaceholderText('Rechercher titre, artiste, album, genre…');self.search.textChanged.connect(self.refresh);self.search.returnPressed.connect(self.submit_search);self.search.setMaximumWidth(340);header.addWidget(self.search)
        settings=QPushButton('⚙ Paramètres');settings.clicked.connect(self.settings_dialog);header.addWidget(settings)
        self.content_widget=QWidget();center=QVBoxLayout(self.content_widget);center.setContentsMargins(0,0,0,0)
        self.heading=QLabel('Ma bibliothèque');self.heading.setStyleSheet('font-size:23px;font-weight:700');center.addWidget(self.heading)
        self.servicebar_widget=QWidget();self.servicebar=QHBoxLayout(self.servicebar_widget);self.servicebar.setContentsMargins(0,0,0,0);center.addWidget(self.servicebar_widget);self.service_buttons=[];self.servicebar_widget.hide()
        # Persistent skin chrome: theme changes only move these existing widgets.
        self.skin_guide=QWidget();guide=QHBoxLayout(self.skin_guide);guide.setContentsMargins(0,0,0,0);guide.addWidget(QLabel('Media Guide  |  Copy to CD or Device  |  Now Playing'));guide.addStretch()
        self.skin_tabs_widget=QWidget();skin_tabs=QHBoxLayout(self.skin_tabs_widget);skin_tabs.setContentsMargins(18,5,18,5)
        for label in ['Now Playing','Library','Rip','Burn','Sync']:skin_tabs.addWidget(QPushButton(label))
        skin_tabs.addStretch()
        bar=QHBoxLayout();self.groupbox=QComboBox();self.groupbox.addItems(['Albums','Artistes','Titres','Genres','Années']);self.groupbox.setCurrentText(self.group);self.groupbox.currentTextChanged.connect(self.group_changed);bar.addWidget(self.groupbox)
        self.playlistbox=QComboBox();self.playlistbox.setVisible(False);self.playlistbox.currentTextChanged.connect(self.select_playlist);bar.addWidget(self.playlistbox);bar.addStretch();self.count=QLabel('0 éléments');bar.addWidget(self.count)
        self.addpl=QPushButton('＋ Créer playlist');self.addpl.clicked.connect(self.create_playlist);bar.addWidget(self.addpl);center.addLayout(bar)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['#','Titre / groupe','Artiste','Album','Genre / année','Durée']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);self.table.cellDoubleClicked.connect(self.play_row);self.table.cellClicked.connect(self.cell_clicked);center.addWidget(self.table,1)
        self.now_panel=QFrame();self.now_panel.setObjectName('card');self.track_title=QLabel('Aucun titre');self.track_title.setStyleSheet('font-weight:700;font-size:17px');self.track_title.setWordWrap(True)
        self.track_artist=QLabel('Ajoutez un dossier musical pour commencer');self.track_artist.setWordWrap(True)
        self.art=QLabel('♫');self.art.setAlignment(Qt.AlignCenter);self.art.setMinimumHeight(88);self.art.setMaximumHeight(160);self.art.setMinimumWidth(120)
        self.visualizer=NowPlayingVisualizer()
        now=QVBoxLayout(self.now_panel);now.addWidget(QLabel('NOW PLAYING'));now.addWidget(self.track_title);now.addWidget(self.track_artist);now.addWidget(self.art);now.addWidget(self.visualizer)
        self.seek=SeekSlider(Qt.Horizontal);self.seek.setRange(0,0);self.seek.sliderPressed.connect(self.seek_pressed);self.seek.sliderMoved.connect(self.seek_preview);self.seek.sliderReleased.connect(self.seek_released)
        self.elapsed=QLabel('0:00');self.total=QLabel('0:00')
        self.shuffle_btn=QPushButton('🔀 Aléatoire');self.shuffle_btn.setCheckable(True);self.shuffle_btn.setChecked(bool(self.cfg['shuffle']));self.shuffle_btn.clicked.connect(self.set_shuffle)
        self.prev=MediaControlButton('previous');self.prev.clicked.connect(lambda:self.step(-1));self.toggle=MediaControlButton('play');self.toggle.setText('▶');self.toggle.clicked.connect(self.play_pause);self.next=MediaControlButton('next');self.next.clicked.connect(lambda:self.step(1));self.stop_btn=MediaControlButton('stop');self.stop_btn.clicked.connect(self.player.stop)
        self.repeat_btn=QPushButton('↻ '+self.cfg['repeat']);self.repeat_btn.clicked.connect(self.cycle_repeat)
        self.vol=QSlider(Qt.Horizontal);self.vol.setRange(0,100);self.vol.setValue(int(self.cfg['volume']));self.vol.valueChanged.connect(self.volume);self.vol.setMaximumWidth(140)
        self.transport=QFrame();self.transport.setObjectName('transport');tr=QVBoxLayout(self.transport);tr.setContentsMargins(10,7,10,7)
        tr.addWidget(self.seek);times=QHBoxLayout();times.addWidget(self.elapsed);times.addStretch();times.addWidget(self.total);tr.addLayout(times)
        cmds=QHBoxLayout();cmds.addStretch()
        for w in [self.shuffle_btn,self.prev,self.toggle,self.next,self.stop_btn,self.repeat_btn,QLabel('Volume'),self.vol]:cmds.addWidget(w)
        cmds.addStretch();tr.addLayout(cmds)
        # Keep QWidget's root layout alive for its entire lifetime. Deleting an
        # installed layout after setParent(None) can leave QWidget::layout()
        # dangling and abort on subsequent re-layouts in Qt/PySide6.
        self.root_layout=QVBoxLayout(self.root);self.root_layout.setContentsMargins(0,0,0,0);self.root_layout.setSpacing(0)
        self._build_skin_layout()

    def _clear_skin_layout(self, layout):
        """Detach persistent widgets and destroy only disposable nested layouts."""
        from shiboken6 import delete as qt_delete
        while layout.count():
            item=layout.takeAt(0)
            widget=item.widget()
            child_layout=item.layout()
            if widget is not None:
                widget.setParent(None)
            elif child_layout is not None:
                self._clear_skin_layout(child_layout)
                child_layout.setParent(None)
                qt_delete(child_layout)
            del item

    def _build_skin_layout(self):
        """Recompose the skin using live widgets and a permanent root layout."""
        name=self.cfg.get('theme','Windows Vista/7 Aero')
        self._clear_skin_layout(self.root_layout)
        if name=='Windows Media Player 7/8':
            outer=QHBoxLayout();outer.setContentsMargins(9,9,9,9);self.root_layout.addLayout(outer);outer.addWidget(self.nav_panel)
            main=QVBoxLayout();outer.addLayout(main,1);main.addWidget(self.header_widget);main.addWidget(self.content_widget,1)
            main.addWidget(self.now_panel);main.addWidget(self.transport)
        elif name=='Windows Media Player 9/10 XP Luna':
            outer=QVBoxLayout();outer.setContentsMargins(10,8,10,10);self.root_layout.addLayout(outer)
            outer.addWidget(self.header_widget)
            outer.addWidget(self.skin_guide)
            body=QHBoxLayout();outer.addLayout(body,1);body.addWidget(self.nav_panel)
            # The playlist/library remains the right-hand pane while Now Playing is prominent.
            body.addWidget(self.now_panel,1);body.addWidget(self.content_widget,2)
            outer.addWidget(self.transport)
        elif name=='Windows Media Player 11 Vista':
            outer=QVBoxLayout();outer.setContentsMargins(0,0,0,0);self.root_layout.addLayout(outer)
            self.header_widget.setObjectName('glossyHeader');outer.addWidget(self.header_widget)
            outer.addWidget(self.skin_tabs_widget)
            body=QHBoxLayout();body.setContentsMargins(12,8,12,8);outer.addLayout(body,1);body.addWidget(self.nav_panel)
            body.addWidget(self.now_panel,1);body.addWidget(self.content_widget,2)
            outer.addWidget(self.transport)
        elif name=='Windows Media Player 12 Windows 10':
            outer=QVBoxLayout();outer.setContentsMargins(14,12,14,10);self.root_layout.addLayout(outer);outer.addWidget(self.header_widget)
            body=QHBoxLayout();outer.addLayout(body,1);body.addWidget(self.nav_panel);body.addWidget(self.content_widget,1)
            outer.addWidget(self.transport)
        elif name=='Windows 10/11 Metro/Fluent':
            outer=QVBoxLayout();outer.setContentsMargins(12,10,12,10);self.root_layout.addLayout(outer);outer.addWidget(self.header_widget)
            body=QHBoxLayout();outer.addLayout(body,1);body.addWidget(self.nav_panel);body.addWidget(self.content_widget,1)
            outer.addWidget(self.now_panel);outer.addWidget(self.transport)
        else: # legacy Vista/7 Aero, Sombre, Clair: classic glass-era layout
            outer=QVBoxLayout();outer.setContentsMargins(12,10,12,10);self.root_layout.addLayout(outer);outer.addWidget(self.header_widget)
            body=QHBoxLayout();outer.addLayout(body,1);body.addWidget(self.nav_panel);body.addWidget(self.content_widget,1)
            playerrow=QHBoxLayout();playerrow.addWidget(self.now_panel,1);playerrow.addWidget(self.transport,2);outer.addLayout(playerrow)
        self._style_transport(name)

    def _style_transport(self,name):
        if name=='Windows Media Player 9/10 XP Luna':
            self.toggle.setFixedSize(62,62);self.toggle.setStyleSheet('border-radius:31px;font-size:23px;font-weight:bold;background:qradialgradient(cx:.35,cy:.3,radius:.9,stop:0 #ffffff,stop:.38 #79b8fa,stop:1 #1458a4);color:white;border:2px solid #d8ebff;')
        elif name=='Windows Media Player 11 Vista':
            self.toggle.setFixedSize(58,58);self.toggle.setStyleSheet('border-radius:29px;font-size:22px;background:qradialgradient(cx:.35,cy:.3,radius:.9,stop:0 #ffffff,stop:.35 #7fd4ff,stop:1 #0075c9);color:white;border:2px solid #d9f2ff;')
        elif name=='Windows Media Player 7/8':
            self.toggle.setFixedSize(48,38);self.toggle.setStyleSheet('border-radius:10px;font-size:19px;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #fff,stop:1 #a9b4c0);border:1px solid #788795;')
        else:
            self.toggle.setFixedSize(42,36);self.toggle.setStyleSheet('')
        for button in (self.prev,self.next,self.shuffle_btn,self.repeat_btn,self.stop_btn):
            button.setMinimumHeight(34)
        if name=='Windows Media Player 11 Vista':
            self.transport.setStyleSheet('QFrame#transport{background:#18232c;border:1px solid #0e161d;border-radius:0;} QFrame#transport QLabel{color:#eef8ff;} QWidget#glossyHeader{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #566a78,stop:.45 #263944,stop:1 #101a22);color:#f1f8fc;}')
        elif name=='Windows Media Player 9/10 XP Luna':
            self.transport.setStyleSheet('QFrame#transport{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e9f4ff,stop:1 #83b6eb);border:1px solid #5182bd;border-radius:13px;}')
        else:self.transport.setStyleSheet('')

    def apply_theme(self,name=None):
        if name in THEMES: self.cfg['theme']=name
        name=self.cfg.get('theme','Windows Vista/7 Aero')
        if name not in THEMES:name='Windows Vista/7 Aero'
        stylesheet=THEMES[name]
        if hasattr(self,'root') and self.cfg.get('theme')!=name:self.cfg['theme']=name
        if hasattr(self,'root'):
            self._build_skin_layout()
        if self.cfg.get('dark_mode') and name!='Sombre':
            if name=='Windows Vista/7 Aero':
                stylesheet += " QMainWindow,QWidget{background:#172331;color:#e5edf5;} QFrame#card,QTableWidget,QListWidget{background:#202f40;color:#e5edf5;border-color:#3f5870;} QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #435b70,stop:1 #293c50);color:#f4f8fc;border-color:#526f88;} QPushButton:hover{background:#405d77;} QLineEdit,QComboBox,QPlainTextEdit{background:#202f40;color:#f4f8fc;border-color:#435d75;} QHeaderView::section{background:#2a3d50;color:#f4f8fc;} QSlider::groove:horizontal{background:#3c5369;}"
            else:
                stylesheet += " QMainWindow,QWidget{background:#17191d;color:#e7e9ee;} QFrame#card,QTableWidget,QListWidget{background:#22252b;color:#e7e9ee;border-color:#363a43;} QPushButton{background:#30343c;color:#eee;border-color:#414650;} QPushButton:hover{background:#414955;} QLineEdit,QComboBox,QPlainTextEdit{background:#22252b;color:#eee;border-color:#414650;} QHeaderView::section{background:#30343c;color:#eee;} QSlider::groove:horizontal{background:#3c414a;}"
        accent=ACCENTS.get(self.cfg.get('accent_color'),'#0078d4');self.setStyleSheet(stylesheet+f" QPushButton:checked{{border:2px solid {accent};}} QSlider::handle:horizontal{{background:{accent};}} QTabBar::tab:selected{{color:{accent};}}")
        if hasattr(self,'shuffle_btn'):self.shuffle_btn.setChecked(bool(self.cfg['shuffle']))
        writecfg(self.cfg)
    def setcfg(self,key,value):self.cfg[key]=value;writecfg(self.cfg)
    def set_accent(self,value):self.cfg['accent_color']=value;self.apply_theme(self.cfg['theme'])
    def navigate(self,name):
        self.page=name;self.active_playlist=None
        self.heading.setText({'Bibliothèque':'Ma bibliothèque','Accueil':'Accueil','Musique locale':'Musique locale','Playlists':'Playlists','Favoris':'Favoris','Lectures récentes':'Lectures récentes','YouTube Music':'YouTube','SoundCloud':'SoundCloud'}.get(name,name))
        for n,b in self.nav:b.setChecked(n==name)
        remote=name in ('YouTube Music','SoundCloud','pCloud','WebDAV','SMB','FTP')
        is_service=name in ('YouTube Music','SoundCloud')
        self.servicebar_widget.setVisible(is_service) if hasattr(self,'servicebar_widget') else None
        self.groupbox.setVisible(not remote and name not in ('Playlists','Favoris','Lectures récentes'));self.playlistbox.setVisible(name=='Playlists');self.addpl.setVisible(name in ('Bibliothèque','Musique locale','Playlists'))
        self.show_service_sections(name) if is_service else None
        if is_service:self.browse_service(name,self.service_section.get(name,'Accueil'))
        elif remote and name=='pCloud':self.pcloud_pending_action=('list',(self.search.text().strip(),));self.launch(self.pcloud_list,self.search.text().strip())
        elif remote:self.rows=[];self.render([]);self.statusBar().showMessage('Profil distant configurable dans Paramètres.',5000)
        else:self.refresh()
    def show_service_sections(self,service):
        self.servicebar_widget.show()
        self.servicebar_widget.setVisible(True)
        sections=['Accueil','Playlists','Uploads','Historique','Aimé']
        while self.servicebar.count():
            item=self.servicebar.takeAt(0);widget=item.widget()
            if widget:widget.deleteLater()
        self.service_buttons=[]
        for section in sections:
            b=QPushButton(section);b.setCheckable(True);b.setChecked(self.service_section.get(service,'Accueil')==section);b.clicked.connect(lambda checked=False,x=section:self.set_service_section(x));self.servicebar.addWidget(b);self.service_buttons.append(b)
        self.servicebar.addStretch()
    def set_service_section(self,section):
        self.service_section[self.page]=section
        self.search.clear();self.browse_service(self.page,section)
    def browse_service(self,service,section):
        self.rows=[];self.render([])
        cookie=self.cfg.get('youtube_cookie' if service=='YouTube Music' else 'soundcloud_cookie','')
        browser=self.cfg.get('youtube_browser' if service=='YouTube Music' else 'soundcloud_browser','')
        user=self.cfg.get('soundcloud_username','') if service=='SoundCloud' else ''
        handle=self.cfg.get('youtube_handle','') if service=='YouTube Music' else ''
        history=self.cfg.get('soundcloud_history',[]) if service=='SoundCloud' else []
        self.service_job=True;self.launch(self.ytdlp_browse_task,service,section,cookie,browser,user,handle,history)
    @staticmethod
    def ytdlp_browse_task(service,section,cookie,browser,user,handle='',history=None):return ytdlp_browse(service,section,cookie,browser,user,handle,history)
    def group_changed(self,value):self.group=value;self.refresh()
    def base_rows(self):
        with sqlite3.connect(DB) as d:d.row_factory=sqlite3.Row;return [dict(x) for x in d.execute('SELECT * FROM tracks')]
    def refresh(self,*_):
        if self.page in ('YouTube Music','SoundCloud','pCloud','WebDAV','SMB','FTP'):return
        rows=self.base_rows();q=self.search.text().strip().casefold()
        if q:rows=[r for r in rows if q in ' '.join(str(r.get(k) or '') for k in ('title','artist','album','genre','year')).casefold()]
        if self.page=='Favoris':rows=[r for r in rows if r.get('favorite')]
        if self.page=='Lectures récentes':
            with sqlite3.connect(DB) as d:played={p:t for p,t in d.execute('SELECT path,played FROM recent')}
            rows=[r for r in rows if r['path'] in played];rows.sort(key=lambda r:played.get(r['path'],0),reverse=True)
        elif self.page=='Playlists':
            if self.active_playlist:
                with sqlite3.connect(DB) as d:d.row_factory=sqlite3.Row;rows=[dict(x) for x in d.execute('SELECT t.* FROM tracks t JOIN playlist_tracks p ON p.path=t.path WHERE p.name=? ORDER BY p.position',(self.active_playlist,))]
            else:rows=[]
        elif self.page not in ('Favoris','Lectures récentes'):
            rows.sort(key=lambda r:(r.get('artist') or '',r.get('album') or '',r.get('title') or ''))
            if self.group!='Titres' and self.page in ('Bibliothèque','Musique locale','Accueil'):
                key={'Albums':'album','Artistes':'artist','Genres':'genre','Années':'year'}[self.group];groups={}
                for r in rows:groups.setdefault(r.get(key) or 'Inconnu',[]).append(r)
                rows=[]
                for name,items in sorted(groups.items(),key=lambda x:x[0].casefold()):
                    r=dict(items[0]);r['title']=name;r['artist']=items[0].get('artist','') if key=='album' else f'{len(items)} titres';r['album']=items[0].get('album','') if key!='album' else f'{len(items)} titres';r['_members']=items;rows.append(r)
        self.render(rows)
        if self.page=='Playlists':self.refresh_playlists()
    def render(self,rows):
        self.rows=rows;self.table.setRowCount(len(rows));self.count.setText(f'{len(rows)} élément(s)')
        for i,r in enumerate(rows):
            vals=[str(i+1),('★ ' if r.get('favorite') else '☆ ')+r.get('title',''),r.get('artist',''),r.get('album',''),f"{r.get('genre','')} · {r.get('year','')}",self.fmt(r.get('duration',0))]
            for j,v in enumerate(vals):
                it=QTableWidgetItem(str(v));it.setData(Qt.UserRole,i);self.table.setItem(i,j,it)
    def refresh_playlists(self):
        with sqlite3.connect(DB) as d:names=[x[0] for x in d.execute('SELECT name FROM playlists ORDER BY name')]
        old=self.active_playlist;self.playlistbox.blockSignals(True);self.playlistbox.clear();self.playlistbox.addItems(names)
        if old in names:self.playlistbox.setCurrentText(old)
        self.playlistbox.blockSignals(False)
        if names and not self.active_playlist:self.active_playlist=names[0];self.playlistbox.setCurrentText(names[0]);self.refresh()
    def select_playlist(self,name):
        if name:self.active_playlist=name;self.refresh()
    def create_playlist(self):
        name,ok=QInputDialog.getText(self,'Créer une playlist','Nom :')
        if not ok or not name.strip():return
        name=name.strip()
        with sqlite3.connect(DB) as d:
            d.execute('INSERT OR IGNORE INTO playlists(name) VALUES(?)',(name,))
            for pos,idx in enumerate(sorted(set(i.row() for i in self.table.selectedIndexes()))):
                if idx<len(self.rows):
                    for item in self.rows[idx].get('_members',[self.rows[idx]]):
                        if item.get('path'):d.execute('INSERT OR IGNORE INTO playlist_tracks VALUES(?,?,?)',(name,item['path'],pos))
        self.active_playlist=name;self.refresh_playlists();self.refresh();self.statusBar().showMessage('Playlist créée',4000)
    def add_folders(self):
        path=QFileDialog.getExistingDirectory(self,'Choisir un dossier musical')
        if not path:return
        QApplication.setOverrideCursor(Qt.WaitCursor);n=0
        try:
            for root,dirs,files in os.walk(path):
                for f in files:
                    fp=os.path.join(root,f)
                    if Path(f).suffix.lower() in EXTS:
                        r=metadata(fp)
                        with sqlite3.connect(DB) as d:d.execute('''INSERT INTO tracks(id,path,title,artist,album,genre,year,duration,art,added) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET title=excluded.title,artist=excluded.artist,album=excluded.album,genre=excluded.genre,year=excluded.year,duration=excluded.duration,art=COALESCE(excluded.art,tracks.art)''',(str(uuid.uuid5(uuid.NAMESPACE_URL,fp)),fp,r['title'],r['artist'],r['album'],r['genre'],r['year'],r['duration'],r['art'],time.time()))
                        n+=1
            if path not in self.cfg['library_folders']:self.cfg['library_folders'].append(path);writecfg(self.cfg)
        finally:QApplication.restoreOverrideCursor()
        self.refresh();self.statusBar().showMessage(f'Analyse terminée : {n} fichiers indexés'+(' (Mutagen indisponible : tags limités aux noms de fichiers)' if MutagenFile is None else ''),8000)
    def cell_clicked(self,row,col):
        if col!=1 or row>=len(self.rows):return
        item=self.rows[row]
        if item.get('path'):
            with sqlite3.connect(DB) as d:d.execute('UPDATE tracks SET favorite=1-favorite WHERE path=?',(item['path'],))
            self.refresh()
    def play_row(self,row,col):
        if row>=len(self.rows):return
        r=self.rows[row]
        if r.get('remote'):
            if r.get('service')=='pCloud':self.pcloud_pending_action=('link',(r,));self.launch(self.pcloud_link,r)
            else:self.launch(ytdlp_stream,r,self.cfg.get('youtube_cookie' if r.get('service')=='YouTube Music' else 'soundcloud_cookie',''),self.cfg.get('youtube_browser' if r.get('service')=='YouTube Music' else 'soundcloud_browser',''))
            self.pending_item=r;return
        members=r.get('_members',[r]);self.queue=members;self.current=0;self.play_item(members[0])
    def play_item(self,item):
        self.current_item=item;self.player.setSource(QUrl.fromLocalFile(item['path']));self.player.setPlaybackRate(float(self.cfg.get('playback_speed',1.0)));self.player.play();self.show_track(item)
        with sqlite3.connect(DB) as d:d.execute('INSERT OR REPLACE INTO recent VALUES(?,?)',(item['path'],time.time()))
    def show_track(self,item):
        self.track_title.setText(item.get('title',''));self.track_artist.setText((item.get('artist') or '')+' · '+(item.get('album') or ''))
        self.art.clear()
        if self.cfg.get('show_artwork') and item.get('art'):
            pix=QPixmap();pix.loadFromData(item['art']);self.art.setPixmap(pix.scaled(QSize(80,80),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        else:self.art.setText('♫')
        if self.tray:self.tray.setToolTip(APP+' · '+item.get('title',''))
    def step(self,n):
        queue=getattr(self,'queue',self.rows)
        if not queue:return
        if self.cfg.get('shuffle') and n>0 and len(queue)>1:
            nxt=self.current
            while nxt==self.current:nxt=random.randrange(len(queue))
        else:nxt=(self.current+n)%len(queue)
        self.current=nxt;self.play_item(queue[nxt])
    def play_pause(self):
        if self.player.playbackState()==QMediaPlayer.PlayingState:self.player.pause()
        elif self.current_item:self.player.play()
        elif self.rows:self.play_row(0,0)
    def set_shuffle(self,on):self.cfg['shuffle']=bool(on);writecfg(self.cfg)
    def cycle_repeat(self):
        opts=['Off','Tout','Un'];self.cfg['repeat']=opts[(opts.index(self.cfg.get('repeat','Off'))+1)%len(opts)];self.repeat_btn.setText('↻ '+self.cfg['repeat']);writecfg(self.cfg)
    def media_status(self,status):
        if status==QMediaPlayer.EndOfMedia:
            if self.cfg.get('repeat')=='Un':self.player.setPosition(0);self.player.play()
            elif self.cfg.get('repeat')=='Tout' or self.cfg.get('shuffle'):self.step(1)
            elif getattr(self,'current',-1)<len(getattr(self,'queue',[]))-1:self.step(1)
    def playstate(self,state):self.toggle.setText('⏸' if state==QMediaPlayer.PlayingState else '▶')
    def seek_pressed(self):self.dragging=True
    def seek_preview(self,v):
        if self.dragging:self.elapsed.setText(self.fmt(v))
    def seek_released(self):
        self.dragging=False
        if self.player.isSeekable():self.player.setPosition(int(self.seek.value())*1000)
    def position(self,p):
        if not self.dragging:
            self.seek.blockSignals(True);self.seek.setValue(min(self.seek.maximum(),max(0,int(p//1000))));self.seek.blockSignals(False);self.elapsed.setText(self.fmt(p/1000))
    def duration(self,d):
        seconds=max(0,min(2147483647,int(d//1000)));self.seek.setRange(0,seconds);self.total.setText(self.fmt(d/1000));self.seek.setEnabled(seconds>0 and self.player.isSeekable())
    def seekability_changed(self,seekable):self.seek.setEnabled(bool(seekable) and self.seek.maximum()>0)
    @staticmethod
    def fmt(sec):sec=int(sec or 0);return f'{sec//60}:{sec%60:02d}'
    def volume(self,v):self.audio.setVolume(v/100);self.cfg['volume']=v;writecfg(self.cfg)
    def player_error(self,*_):self.cfg['last_error']=self.player.errorString();writecfg(self.cfg);self.statusBar().showMessage('Erreur audio : '+self.cfg['last_error'],10000)
    def launch(self,fn,*args):
        job=Job(fn,*args);self.jobs.append(job);job.signals.done.connect(self.async_done);job.signals.error.connect(self.async_error);job.signals.done.connect(lambda _,j=job:self.forget(j));job.signals.error.connect(lambda _,j=job:self.forget(j));self.statusBar().showMessage('Connexion/recherche en cours…');self.pool.start(job)
    def forget(self,j):
        if j in self.jobs:self.jobs.remove(j)
    def submit_search(self):
        if self.page in ('YouTube Music','SoundCloud'):self.search_service(self.page)
        elif self.page in ('Bibliothèque','Musique locale','Accueil'):self.refresh()
    def search_service(self,service=None):
        service=service or self.page;q=self.search.text().strip()
        if not q:return
        if service=='pCloud':self.pcloud_pending_action=('list',(q,));self.launch(self.pcloud_list,q)
        elif service in ('YouTube Music','SoundCloud'):
            self.service_job=False;self.servicebar_widget.hide();cookie=self.cfg.get('youtube_cookie' if service=='YouTube Music' else 'soundcloud_cookie','');browser=self.cfg.get('youtube_browser' if service=='YouTube Music' else 'soundcloud_browser','');self.launch(ytdlp_search,q,service,cookie,browser)
        else:self.statusBar().showMessage('Les profils WebDAV/SMB/FTP sont configurables dans Paramètres.')
    def async_done(self,result):
        if isinstance(result,dict) and result.get('pcloud_2fa_required'):
            code,ok=QInputDialog.getText(self,'Vérification pCloud','Code de vérification à deux facteurs :')
            if not ok or not code.strip():
                self.statusBar().showMessage('Connexion pCloud annulée : code 2FA non fourni.',8000);return
            self.launch(self.pcloud_tfa_login,result['token'],code.strip());return
        if isinstance(result,dict) and 'browse_entries' in result:
            if getattr(self,'service_job',False):self.servicebar_widget.setVisible(self.page in ('YouTube Music','SoundCloud'))
            rows=result['browse_entries'];self.render(rows);self.service_job=False
            self.statusBar().showMessage(result.get('notice') or f'{len(rows)} résultat(s)',10000 if result.get('notice') else 5000);return
        if isinstance(result,list):
            if getattr(self,'service_job',False):self.servicebar_widget.setVisible(self.page in ('YouTube Music','SoundCloud'))
            self.render(result);self.statusBar().showMessage(f'{len(result)} résultat(s)',5000);self.service_job=False
        elif isinstance(result,dict) and result.get('pcloud_auth'):
            self.setcfg('pcloud_token',result['pcloud_auth'])
            action,args=getattr(self,'pcloud_pending_action',('list',(self.search.text().strip(),)))
            self.statusBar().showMessage('Connexion pCloud vérifiée et jeton enregistré.',5000)
            self.launch(self.pcloud_list,*args) if action=='list' else self.launch(self.pcloud_link,*args)
        elif isinstance(result,dict) and result.get('url'):
            item=getattr(self,'pending_item',{});item.update(result);self.current_item=item;self.player.setSource(QUrl(result['url']));self.player.play();self.show_track(item)
            if item.get('service')=='SoundCloud':
                history=[x for x in self.cfg.get('soundcloud_history',[]) if x.get('webpage_url')!=item.get('webpage_url')]
                history.insert(0,{k:item.get(k) for k in ('title','artist','album','duration','webpage_url','id')});self.setcfg('soundcloud_history',history[:100])
    def async_error(self,msg):
        if getattr(self,'service_job',False):self.servicebar_widget.setVisible(self.page in ('YouTube Music','SoundCloud'))
        self.service_job=False;self.cfg['last_error']=msg;writecfg(self.cfg);self.statusBar().showMessage('Erreur de service : '+msg,10000)
    def settings_dialog(self):
        dlg=QDialog(self);dlg.setWindowTitle('Paramètres');dlg.resize(690,700);layout=QVBoxLayout(dlg);tabs=QTabWidget();layout.addWidget(tabs)
        general=QWidget();form=QFormLayout(general);theme=QComboBox();theme.addItems(['Windows Media Player 7/8','Windows Media Player 9/10 XP Luna','Windows Media Player 11 Vista','Windows Media Player 12 Windows 10','Windows Vista/7 Aero','Windows 10/11 Metro/Fluent','Sombre','Clair']);theme.setCurrentText(self.cfg['theme']);theme.currentTextChanged.connect(self.apply_theme);form.addRow('Thème (application immédiate)',theme)
        dark=QCheckBox('Mode sombre');dark.setChecked(bool(self.cfg.get('dark_mode',False)));dark.toggled.connect(lambda v:(self.setcfg('dark_mode',v),self.apply_theme()));form.addRow('Apparence',dark)
        accent=QComboBox();accent.addItems(ACCENTS);accent.setCurrentText(self.cfg.get('accent_color','Bleu'));accent.currentTextChanged.connect(self.set_accent);form.addRow('Couleur d’accentuation',accent)
        visible=QLineEdit(', '.join(self.cfg.get('visible_sources',[])));visible.editingFinished.connect(lambda:self.setcfg('visible_sources',[x.strip() for x in visible.text().split(',') if x.strip()]));form.addRow('Sources visibles (séparées par des virgules)',visible)
        for label,key in [('Afficher les pochettes','show_artwork'),('Qualité audio élevée','high_audio_quality'),('Ignorer les silences','skip_silence'),('Mémoriser vitesse/tonalité','remember_playback_parameters')]:
            cb=QCheckBox();cb.setChecked(bool(self.cfg.get(key)));cb.toggled.connect(lambda v,k=key:self.setcfg(k,v));form.addRow(label,cb)
        speed=QDoubleSpinBox();speed.setRange(.5,2);speed.setSingleStep(.05);speed.setValue(float(self.cfg.get('playback_speed',1)));speed.valueChanged.connect(lambda v:self.setcfg('playback_speed',v));form.addRow('Vitesse de lecture',speed)
        pitch=QDoubleSpinBox();pitch.setRange(.5,2);pitch.setSingleStep(.05);pitch.setValue(float(self.cfg.get('playback_pitch',1)));pitch.valueChanged.connect(lambda v:self.setcfg('playback_pitch',v));form.addRow('Tonalité (valeur mémorisée)',pitch);tabs.addTab(general,'Général')
        services=QWidget();sf=QFormLayout(services)
        cookie=QLineEdit(self.cfg.get('youtube_cookie',''));cookie.editingFinished.connect(lambda:self.setcfg('youtube_cookie',cookie.text()));sf.addRow('Fichier cookies YouTube',cookie);pick=QPushButton('Parcourir…');pick.clicked.connect(lambda:self.pick_cookie(cookie,'youtube_cookie'));sf.addRow(pick)
        ybrowser=QComboBox();ybrowser.addItems(['','chrome','firefox','edge','brave','opera','vivaldi']);ybrowser.setCurrentText(self.cfg.get('youtube_browser',''));ybrowser.currentTextChanged.connect(lambda v:self.setcfg('youtube_browser',v));sf.addRow('Cookies YouTube depuis le navigateur',ybrowser)
        scookie=QLineEdit(self.cfg.get('soundcloud_cookie',''));scookie.editingFinished.connect(lambda:self.setcfg('soundcloud_cookie',scookie.text()));sf.addRow('Fichier cookies SoundCloud',scookie);spick=QPushButton('Parcourir…');spick.clicked.connect(lambda:self.pick_cookie(scookie,'soundcloud_cookie'));sf.addRow(spick)
        sbrowser=QComboBox();sbrowser.addItems(['','chrome','firefox','edge','brave','opera','vivaldi']);sbrowser.setCurrentText(self.cfg.get('soundcloud_browser',''));sbrowser.currentTextChanged.connect(lambda v:self.setcfg('soundcloud_browser',v));sf.addRow('Cookies SoundCloud depuis le navigateur',sbrowser)
        scuser=QLineEdit(self.cfg.get('soundcloud_username',''));scuser.editingFinished.connect(lambda:self.setcfg('soundcloud_username',soundcloud_permalink(scuser.text())));sf.addRow('Profil SoundCloud (nom ou URL)',scuser)
        yhandle=QLineEdit(self.cfg.get('youtube_handle',''));yhandle.setPlaceholderText('@identifiant ou URL de chaîne');yhandle.editingFinished.connect(lambda:self.setcfg('youtube_handle',yhandle.text().strip()));sf.addRow('Chaîne YouTube pour Uploads (optionnel)',yhandle)
        region=QComboBox();region.addItems(['US','EU']);region.setCurrentText(self.cfg.get('pcloud_region','US'));region.currentTextChanged.connect(lambda v:self.setcfg('pcloud_region',v));sf.addRow('Région pCloud',region)
        for key,label,secret in [('pcloud_username','Nom d’utilisateur pCloud',False),('pcloud_password','Mot de passe pCloud',True),('pcloud_token','Jeton d’accès pCloud (optionnel)',True)]:
            le=QLineEdit(self.cfg.get(key,''));le.setEchoMode(QLineEdit.Password if secret else QLineEdit.Normal);le.editingFinished.connect(lambda k=key,w=le:self.setcfg(k,w.text()));sf.addRow(label,le)
        sf.addRow(QLabel('Les identifiants sont stockés localement dans settings.json.'))
        profiles=QPlainTextEdit();profiles.setPlainText(json.dumps(self.cfg.get('remote_profiles',[]),ensure_ascii=False,indent=2));profiles.setMinimumHeight(120);sf.addRow('Profils WebDAV / SMB / FTP (JSON)',profiles)
        def save_profiles():
            try:
                data=json.loads(profiles.toPlainText())
                if not isinstance(data,list):raise ValueError('La racine doit être une liste JSON.')
                self.setcfg('remote_profiles',data)
            except Exception as e:self.statusBar().showMessage(f'Profils non enregistrés : {e}',8000)
        profiles.textChanged.connect(save_profiles);tabs.addTab(services,'Services')
        tray=QCheckBox('Icône dans la zone de notification');tray.setChecked(bool(self.cfg['tray_enabled']));tray.toggled.connect(self.setup_tray);prefs=QWidget();pf=QVBoxLayout(prefs);pf.addWidget(tray);pf.addStretch();tabs.addTab(prefs,'Fenêtre')
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        close=QPushButton('Fermer');close.clicked.connect(dlg.close);layout.addWidget(close);dlg.exec()
    def pick_cookie(self,line,key='youtube_cookie'):
        path,_=QFileDialog.getOpenFileName(self,'Choisir le fichier cookies','', 'Fichiers cookies (*.txt);;Tous les fichiers (*)')
        if path:line.setText(path);self.setcfg(key,path)
    def pcloud_api(self,endpoint,params):
        host='https://api.pcloud.com' if self.cfg.get('pcloud_region','US')=='US' else 'https://eapi.pcloud.com';endpoint=endpoint.lstrip('/');r=requests.get(f'{host}/{endpoint}',params=params,timeout=25);r.raise_for_status()
        try:data=r.json()
        except ValueError:raise RuntimeError(f'pCloud a renvoyé une réponse non JSON (HTTP {r.status_code}).')
        if data.get('result')!=0:
            code=data.get('result');message=data.get('error','requête échouée')
            if code in (1022,7013):raise PCloud2FARequired(str(data.get('token') or ''))
            if code in (2000,2094):message='authentification expirée ou invalide; reconnectez le compte ou renouvelez le jeton.'
            raise RuntimeError(f'pCloud API {code}: {message}')
        return data
    def pcloud_auth(self):
        token=self.cfg.get('pcloud_token','').strip()
        if token:return token
        user=self.cfg.get('pcloud_username','').strip();pwd=self.cfg.get('pcloud_password','')
        if not user or not pwd:raise RuntimeError('Renseignez un jeton, ou un identifiant et un mot de passe pCloud dans Paramètres.')
        result=self.pcloud_api('userinfo',{'getauth':1,'logout':1,'username':user,'password':pwd})
        auth=result.get('auth')
        if not auth:raise RuntimeError('pCloud n’a retourné aucun jeton d’authentification.')
        self.cfg['pcloud_token']=auth;writecfg(self.cfg);return auth
    def pcloud_tfa_login(self,token,code):
        if not token:raise RuntimeError('pCloud n’a pas fourni de jeton temporaire 2FA; vérifiez la région et réessayez.')
        data=self.pcloud_api('tfa_login',{'token':token,'code':code,'trustdevice':1})
        auth=data.get('auth')
        if not auth:raise RuntimeError('pCloud tfa_login n’a pas retourné de jeton auth.')
        return {'pcloud_auth':auth}
    def pcloud_list(self,query=''):
        auth=self.pcloud_auth();found=[]
        def walk(folder=0,path=''):
            data=self.pcloud_api('listfolder',{'auth':auth,'folderid':folder,'nofiles':0,'recursive':0})
            for x in data.get('metadata',{}).get('contents',[]):
                name=x.get('name','');full=path+'/'+name
                if x.get('isfolder'):walk(x.get('folderid'),full)
                elif Path(name).suffix.lower() in EXTS and (not query or query.casefold() in name.casefold()):found.append({'title':Path(name).stem,'artist':'pCloud','album':full,'duration':0,'remote':True,'service':'pCloud','fileid':x.get('fileid'),'path':full})
        walk();return found
    def pcloud_link(self,item):
        data=self.pcloud_api('getfilelink',{'auth':self.pcloud_auth(),'fileid':item['fileid']});hosts=data.get('hosts') or []
        if not hosts:raise RuntimeError('Aucun hôte pCloud retourné.')
        host=str(hosts[0]).removeprefix('https://').removeprefix('http://').rstrip('/');path=str(data.get('path',''))
        if not path.startswith('/'):path='/'+path
        return {'url':f'https://{host}{path}','title':item['title'],'artist':'pCloud'}
    def setup_tray(self,enabled):
        self.cfg['tray_enabled']=bool(enabled);writecfg(self.cfg)
        if not enabled:
            if self.tray:self.tray.hide();self.tray=None
            self.setWindowFlag(Qt.Tool,False);self.show();return
        if not QSystemTrayIcon.isSystemTrayAvailable():self.statusBar().showMessage('Zone de notification indisponible.');return
        self.setWindowFlag(Qt.Tool,True)
        if not self.tray:
            self.tray=QSystemTrayIcon(self);self.tray.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay));menu=QMenu();play=menu.addAction('Lecture / Pause');play.triggered.connect(self.play_pause);prev=menu.addAction('Précédent');prev.triggered.connect(lambda:self.step(-1));nxt=menu.addAction('Suivant');nxt.triggered.connect(lambda:self.step(1));show=menu.addAction('Afficher');show.triggered.connect(self.show_window);quit=menu.addAction('Quitter');quit.triggered.connect(QApplication.quit);self.tray.setContextMenu(menu);self.tray.activated.connect(self.tray_activated)
        self.tray.show();self.show()
    def tray_activated(self,reason):
        if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick):self.hide() if self.isVisible() else self.show_window()
    def show_window(self):self.showNormal();self.raise_();self.activateWindow()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange and self.isMinimized() and self.cfg.get('tray_enabled') and self.tray:self.hide()
    def closeEvent(self,event):
        if self.cfg.get('tray_enabled') and self.tray and self.tray.isVisible():
            self.hide();event.ignore()
        else:
            event.accept()
            QApplication.quit()

def main():
    try:
        app=QApplication(sys.argv);app.setApplicationName(APP);w=PlayerWindow();w.show();return app.exec()
    except BaseException:
        detail=traceback.format_exc()
        _write_crash(detail)
        _show_crash_message(detail)
        return 1
if __name__=='__main__':sys.exit(main())
