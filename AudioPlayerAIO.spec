# PyInstaller spec, onedir Windows distribution.
import os
from PyInstaller.utils.hooks import collect_all
project_dir = os.path.abspath(SPECPATH)
main_script = os.path.join(project_dir, 'main.py')
pyside_datas, pyside_bins, pyside_hidden = collect_all('PySide6')
mut_datas, mut_bins, mut_hidden = collect_all('mutagen')
ytdlp_datas, ytdlp_bins, ytdlp_hidden = collect_all('yt_dlp')
requests_datas, requests_bins, requests_hidden = collect_all('requests')
a = Analysis([main_script], pathex=[project_dir], binaries=pyside_bins+mut_bins+ytdlp_bins+requests_bins,
 datas=pyside_datas+mut_datas+ytdlp_datas+requests_datas,
 hiddenimports=pyside_hidden+mut_hidden+ytdlp_hidden+requests_hidden+['yt_dlp.extractor.youtube','yt_dlp.extractor.soundcloud'],
 hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AudioPlayerAIO', debug=False,
 bootloader_ignore_signals=False, strip=False, upx=True, console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name='AudioPlayerAIO')
