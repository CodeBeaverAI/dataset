import importlib
import pytest
import setuptools

class TestSetup:
    """Test suite for verifying setup.py configuration."""

    def test_setup_configuration(self, monkeypatch, tmp_path):
        """Test that setup() is called with correct metadata when README.md exists."""
        # Create a dummy README.md file with test content.
        readme = tmp_path / "README.md"
        test_readme = "This is a dummy README for testing."
        readme.write_text(test_readme)

        # Change working directory to tmp_path to pick up the dummy README.
        monkeypatch.chdir(tmp_path)

        # Dummy function to capture the arguments passed to setuptools.setup.
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)

        # Monkey patch setuptools.setup with the dummy_setup.
        monkeypatch.setattr(setuptools, "setup", dummy_setup)

        # Remove setup module from sys.modules to force re-execution of top-level code.
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]

        # Load the setup module to trigger the setup() call.
        import setup
        importlib.reload(setup)

        # Verify that the captured setup arguments contain expected metadata.
        assert captured.get("name") == "dataset"
        assert captured.get("version") == "1.6.0"
        assert captured.get("long_description") == test_readme
        assert "sqlalchemy >= 2.0.15, < 3.0.0" in captured.get("install_requires", [])

    def test_missing_readme(self, monkeypatch, tmp_path):
        """Test that missing README.md file raises FileNotFoundError during module import."""
        # Change working directory to tmp_path which does not contain a README.md.
        monkeypatch.chdir(tmp_path)

        # Remove setup module from sys.modules to force re-execution of top-level code.
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]

        # Verify that loading setup.py without README.md raises FileNotFoundError.
        with pytest.raises(FileNotFoundError):
            import setup
            importlib.reload(setup)
    def test_setup_complete_metadata(self, monkeypatch, tmp_path):
        """Test that setup() is called with complete metadata from setup.py."""
        # Create a dummy README.md file with test content for complete metadata test.
        readme = tmp_path / "README.md"
        test_readme = "Complete metadata test."
        readme.write_text(test_readme)

        # Change working directory to tmp_path so that setup.py picks up our dummy README.
        monkeypatch.chdir(tmp_path)

        # Dummy function to capture the arguments passed to setuptools.setup.
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)

        # Monkey patch setuptools.setup with the dummy_setup.
        monkeypatch.setattr(setuptools, "setup", dummy_setup)

        # Remove setup module from sys.modules to force re-execution of top-level code.
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]

        # Load the setup module to trigger the setup() call.
        import setup
        importlib.reload(setup)

        # Verify that all of the expected metadata keys and values are present in captured setup()
        assert captured.get("name") == "dataset"
        assert captured.get("version") == "1.6.0"
        assert captured.get("description") == "Toolkit for Python-based database access."
        assert captured.get("long_description") == test_readme
        assert isinstance(captured.get("classifiers"), list) and len(captured.get("classifiers")) > 0
        assert captured.get("keywords") == "sql sqlalchemy etl loading utility"
        assert captured.get("author") == "Friedrich Lindenberg, Gregor Aisch, Stefan Wehrmeyer"
        assert captured.get("author_email") == "friedrich.lindenberg@gmail.com"
        assert captured.get("url") == "http://github.com/pudo/dataset"
        assert captured.get("license") == "MIT"
        assert isinstance(captured.get("install_requires"), list)
        assert "sqlalchemy >= 2.0.15, < 3.0.0" in captured.get("install_requires")
        assert captured.get("extras_require") == {
            "dev": [
                "pip",
                "pytest",
                "wheel",
                "flake8",
                "coverage",
                "psycopg2-binary",
                "PyMySQL",
                "cryptography",
            ]
        }
        assert captured.get("tests_require") == ["pytest"]
        assert captured.get("test_suite") == "test"
        # packages is generated via find_packages; we check that a value is present.
        assert captured.get("packages") is not None
        assert captured.get("namespace_packages") == []
        assert captured.get("include_package_data") is False
        assert captured.get("zip_safe") is False
    def test_find_packages_called(self, monkeypatch, tmp_path):
        """Test that the packages parameter is computed using monkeypatched find_packages."""
        readme = tmp_path / "README.md"
        readme.write_text("dummy")
        monkeypatch.chdir(tmp_path)
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)
        monkeypatch.setattr(setuptools, "setup", dummy_setup)
        monkeypatch.setattr(setuptools, "find_packages", lambda exclude: ["dummy_pkg"])
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]
        import setup
        importlib.reload(setup)
        assert captured.get("packages") == ["dummy_pkg"]

    def test_install_requires_length(self, monkeypatch, tmp_path):
        """Test that install_requires contains exactly three dependencies with correct content."""
        readme = tmp_path / "README.md"
        readme.write_text("dummy")
        monkeypatch.chdir(tmp_path)
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)
        monkeypatch.setattr(setuptools, "setup", dummy_setup)
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]
        import setup
        importlib.reload(setup)
        install_requires = captured.get("install_requires")
        assert isinstance(install_requires, list)
        assert len(install_requires) == 3
        assert "sqlalchemy >= 2.0.15, < 3.0.0" in install_requires
        assert "alembic >= 1.11.1" in install_requires
        assert "banal >= 1.0.1" in install_requires
    def test_long_description_content_type(self, monkeypatch, tmp_path):
        """Test that long_description_content_type is set to 'text/markdown'."""
        readme = tmp_path / "README.md"
        readme.write_text("Dummy content for long_description_content_type test")
        monkeypatch.chdir(tmp_path)
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)
        monkeypatch.setattr(setuptools, "setup", dummy_setup)
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]
        import setup
        importlib.reload(setup)
        assert captured.get("long_description_content_type") == "text/markdown"

    def test_entry_points(self, monkeypatch, tmp_path):
        """Test that the entry_points field is an empty dictionary."""
        readme = tmp_path / "README.md"
        readme.write_text("Dummy content for entry_points test")
        monkeypatch.chdir(tmp_path)
        captured = {}
        def dummy_setup(**kwargs):
            captured.update(kwargs)
        monkeypatch.setattr(setuptools, "setup", dummy_setup)
        import sys
        if "setup" in sys.modules:
            del sys.modules["setup"]
        import setup
        importlib.reload(setup)
        assert captured.get("entry_points") == {}