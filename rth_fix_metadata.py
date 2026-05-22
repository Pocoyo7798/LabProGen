import sys
import os

# Ensure PyInstaller's temporary extraction dir is on sys.path so
# importlib.metadata can discover packaged .dist-info directories.
meipass = getattr(sys, "_MEIPASS", None)
if meipass:
    if meipass not in sys.path:
        sys.path.insert(0, meipass)
    site_packages = os.path.join(meipass, "Lib", "site-packages")
    if os.path.isdir(site_packages) and site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    
    # Monkeypatch importlib.metadata.distribution to fallback to any dist-info
    # directories we included under the _MEIPASS folder.
    try:
        import importlib.metadata as _im
        from importlib.metadata import PackageNotFoundError, PathDistribution
    except Exception:
        _im = None

    if _im is not None:
        _orig_dist = _im.distribution

        def _dist_fallback(name, *args, **kwargs):
            try:
                return _orig_dist(name, *args, **kwargs)
            except PackageNotFoundError:
                # look for matching dist-info under _MEIPASS
                mp = os.path.abspath(meipass)
                candidates = []
                for pattern in (f"*{name}*.dist-info", f"*{name.replace('_','-')}*.dist-info", f"*{name.replace('-','_')}*.dist-info"):
                    candidates.extend([p for p in __import__('pathlib').Path(mp).glob(pattern)])
                if candidates:
                    # take first match
                    return PathDistribution(candidates[0])
                raise

        try:
            _im.distribution = _dist_fallback
        except Exception:
            pass
