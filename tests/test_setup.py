import io
import builtins
import pytest
import importlib
import setuptools

# Global dictionary to capture the kwargs passed to setuptools.setup
captured_setup_kwargs = {}

def dummy_setup(*args, **kwargs):
    """Dummy setup function that captures the setup kwargs."""
    captured_setup_kwargs.update(kwargs)

@pytest.fixture(autouse=True, scope="function")
def patch_setup(monkeypatch):
    """Patch setuptools.setup and builtins.open before importing setup.py."""
    # Patch setuptools.setup with our dummy function
    monkeypatch.setattr(setuptools, "setup", dummy_setup)

    # Patch open so that opening "README.md" returns a dummy stream with controlled text
    def dummy_open(filename, *args, **kwargs):
        if filename == "README.md":
            return io.StringIO("Dummy long description")
        return open(filename, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", dummy_open)

    # Import (or reload) the setup module to trigger its top‐level code
    import setup
    importlib.reload(setup)

def test_setup_configuration():
    """Test that setup.py properly calls setuptools.setup with the expected configuration."""
    # Verify the package name and version
    assert captured_setup_kwargs.get("name") == "dataset", "Package name should be 'dataset'"
    assert captured_setup_kwargs.get("version") == "1.6.0", "Version should be '1.6.0'"

    # Verify that the long_description is correctly populated from our dummy README.md
    assert captured_setup_kwargs.get("long_description") == "Dummy long description", \
        "long_description should match dummy content from README.md"

    # Verify that the install_requires includes the expected packages
    install_requires = captured_setup_kwargs.get("install_requires", [])
    assert "sqlalchemy >= 2.0.15, < 3.0.0" in install_requires, \
        "install_requires should include sqlalchemy version range"
    assert "alembic >= 1.11.1" in install_requires, \
        "install_requires should include alembic"
    assert "banal >= 1.0.1" in install_requires, \
        "install_requires should include banal"

    # Verify that extras_require and tests_require are configured
    extras_require = captured_setup_kwargs.get("extras_require", {})
    assert "dev" in extras_require, "extras_require should include the 'dev' option"

    tests_require = captured_setup_kwargs.get("tests_require", [])
    assert "pytest" in tests_require, "tests_require should include 'pytest'"
def test_setup_additional_configuration():
    """Test additional configuration parameters of setup.py."""
    # Test the description field
    assert captured_setup_kwargs.get("description") == "Toolkit for Python-based database access.", "Description mismatch"

    # Test long_description_content_type
    assert captured_setup_kwargs.get("long_description_content_type") == "text/markdown", "long_description_content_type mismatch"

    # Test classifiers: ensure certain known classifiers are present and total count is 9
    classifiers = captured_setup_kwargs.get("classifiers", [])
    expected_classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
    ]
    for classifier in expected_classifiers:
        assert classifier in classifiers, f"Classifier {classifier} not found"
    assert len(classifiers) == 9, "There should be 9 classifiers"

    # Test keywords, author, author_email, url, and license
    assert captured_setup_kwargs.get("keywords") == "sql sqlalchemy etl loading utility", "Keywords mismatch"
    assert captured_setup_kwargs.get("author") == "Friedrich Lindenberg, Gregor Aisch, Stefan Wehrmeyer", "Author mismatch"
    assert captured_setup_kwargs.get("author_email") == "friedrich.lindenberg@gmail.com", "Author email mismatch"
    assert captured_setup_kwargs.get("url") == "http://github.com/pudo/dataset", "URL mismatch"
    assert captured_setup_kwargs.get("license") == "MIT", "License mismatch"

    # Test packages: should return a list and not include excluded packages
    packages = captured_setup_kwargs.get("packages")
    assert isinstance(packages, list), "packages should be a list"
    for pkg in packages:
        assert pkg not in ("ez_setup", "examples", "test"), "Excluded package found"

    # Test namespace_packages, include_package_data, zip_safe, test_suite, and entry_points
    assert captured_setup_kwargs.get("namespace_packages") == [], "namespace_packages should be empty list"
    assert captured_setup_kwargs.get("include_package_data") is False, "include_package_data should be False"
    assert captured_setup_kwargs.get("zip_safe") is False, "zip_safe should be False"
    assert captured_setup_kwargs.get("test_suite") == "test", "test_suite should be 'test'"
    assert captured_setup_kwargs.get("entry_points") == {}, "entry_points should be {}"
def test_extras_require_dev_content():
    """Test that the 'dev' extras in extras_require contain exactly the expected packages."""
    extras_require = captured_setup_kwargs.get("extras_require", {})
    dev_deps = extras_require.get("dev", [])
    expected_deps = [
        "pip",
        "pytest",
        "wheel",
        "flake8",
        "coverage",
        "psycopg2-binary",
        "PyMySQL",
        "cryptography",
    ]
    for dep in expected_deps:
        assert dep in dev_deps, f"dev extras_require missing {dep}"
    # Check that there are no additional dependencies in dev extras
    assert len(dev_deps) == len(expected_deps), "dev extras_require contains unexpected dependencies"

def test_install_requires_is_list_of_strings():
    """Test that install_requires is a list and that each element is a string."""
    install_requires = captured_setup_kwargs.get("install_requires", [])
    assert isinstance(install_requires, list), "install_requires should be a list"
    for requirement in install_requires:
        assert isinstance(requirement, str), "Each install requirement should be a string"
def test_readme_not_found(monkeypatch):
    """Test that missing README.md raises FileNotFoundError during setup module import."""
    # Override open to simulate a missing README.md file
    def missing_open(filename, *args, **kwargs):
        if filename == "README.md":
            raise FileNotFoundError("No README.md found")
        return open(filename, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", missing_open)
    import sys
    if "setup" in sys.modules:
        del sys.modules["setup"]
    with pytest.raises(FileNotFoundError):
        import setup

def test_multiple_reloads(monkeypatch):
    """Test that reloading setup.py multiple times produces consistent configuration."""
    import setup
    captured_first = captured_setup_kwargs.copy()
    importlib.reload(setup)
    captured_second = captured_setup_kwargs.copy()
    assert captured_first == captured_second, "Configuration should be consistent across reloads"