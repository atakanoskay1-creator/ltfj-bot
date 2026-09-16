"""Test kok dizinini sys.path'e ekler ki 'import ltfj_analiz' gibi
satirlar pytest'in nereden calistirildigina bakmaksizin calissin."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
