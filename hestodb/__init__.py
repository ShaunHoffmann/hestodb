# see license/LICENSE.rst
from pathlib import Path

try:
    from ._version import version as __version__
    from ._version import version_tuple
except ImportError:
    __version__ = "unknown version"
    version_tuple = (0, 0, "unknown version")

_package_directory = Path(__file__).parent
_data_directory = _package_directory / "data"
_test_files_directory = _package_directory / "data" / "test"
_test_report_pptx = (
    _test_files_directory / "HESTO-202612_Report_24-HTIDS24_Smith-rev3.pptx"
)
