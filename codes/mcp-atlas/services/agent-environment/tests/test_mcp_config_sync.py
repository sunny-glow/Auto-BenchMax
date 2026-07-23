"""
Unit test to ensure packages in mcp_server_template.json are pre-installed in the install script.

mcp_server_template.json is the source of truth for MCP server packages.
dev_scripts/install_mcp_packages.sh should be updated to match the template.

This test prevents deployment issues where:
- New packages are added to template but forgotten in the install script
- Package versions are updated in template but not in the install script
- Packages are removed from template but left in the install script (causing bloat)

When this test fails: UPDATE THE .SH FILE to match the .JSON template.
"""

import json
from pathlib import Path

try:
    import pytest
except ImportError:
    pytest = None


def load_mcp_config():
    """Load the MCP server template configuration."""
    config_path = (
        Path(__file__).parent.parent
        / "src"
        / "agent_environment"
        / "mcp_server_template.json"
    )
    with open(config_path) as f:
        return json.load(f)


def load_install_script():
    """Load the MCP install script content."""
    script_path = (
        Path(__file__).parent.parent / "dev_scripts" / "install_mcp_packages.sh"
    )
    with open(script_path) as f:
        return f.read()


def extract_packages_from_config():
    """Extract all NPX and UVX packages from template."""
    config = load_mcp_config()
    packages = {"npx": [], "uvx": []}

    for server_name, server_config in config["mcpServers"].items():
        command = server_config.get("command")
        if command in ["npx", "uvx"]:
            args = server_config.get("args", [])
            if args:
                # Get the first argument that looks like a package (skip -y flag)
                package_arg = None
                for arg in args:
                    if not arg.startswith("-") and not arg.startswith("/"):
                        package_arg = arg
                        break

                if package_arg:
                    packages[command].append(package_arg)

    return packages


def extract_packages_from_script():
    """Extract all packages from install script."""
    script_content = load_install_script()
    packages = {"npx": [], "uvx": []}

    # Extract NPX packages (from the big npm install -g block)
    lines = script_content.split("\n")
    in_npm_block = False

    for line in lines:
        line = line.strip()
        if "npm install -g" in line:
            in_npm_block = True
            continue
        if in_npm_block:
            if line and not line.startswith("#") and not line.startswith("echo"):
                if line.endswith(" \\"):
                    # Package line in the install block (continues)
                    package = line.replace(" \\", "").strip()
                    if package and not package.startswith("-") and "@" in package:
                        packages["npx"].append(package)
                elif "@" in line and not line.startswith("-"):
                    # Last package line in the install block (no backslash)
                    package = line.strip()
                    if package:
                        packages["npx"].append(package)
                    in_npm_block = False
                else:
                    in_npm_block = False

    # Extract UVX packages (from uv tool install lines)
    uv_lines = [
        line.strip() for line in lines if line.strip().startswith("uv tool install")
    ]
    for line in uv_lines:
        # Only regular packages: uv tool install package==version
        parts = line.split()
        if len(parts) >= 3:
            package = parts[3]  # The package is the 4th element (index 3)
            if "==" in package:
                packages["uvx"].append(package)

    return packages


def test_package_sync():
    """Test that the install script matches the template (template is source of truth)."""
    config_packages = extract_packages_from_config()
    script_packages = extract_packages_from_script()

    print(f"Config NPX packages: {len(config_packages['npx'])}")
    print(f"Script NPX packages: {len(script_packages['npx'])}")
    print(f"Config UVX packages: {len(config_packages['uvx'])}")
    print(f"Script UVX packages: {len(script_packages['uvx'])}")

    # Check synchronization
    assert len(config_packages["npx"]) > 0, "Should have NPX packages"
    assert len(config_packages["uvx"]) > 0, "Should have UVX packages"
    assert len(script_packages["npx"]) > 0, "Should have NPX packages in script"
    assert len(script_packages["uvx"]) > 0, "Should have UVX packages in script"

    # Check NPX packages from config are in script (excluding Git URLs)
    config_npx_set = set(config_packages["npx"])
    script_npx_set = set(script_packages["npx"])

    # Only check non-Git packages (ones with @ version, not https://)
    config_regular_npx = {
        pkg for pkg in config_npx_set if not pkg.startswith("https://")
    }

    missing_npx = config_regular_npx - script_npx_set

    if missing_npx:
        # Check if it's a version mismatch rather than completely missing
        version_mismatches = []
        truly_missing = []

        for missing_pkg in missing_npx:
            # Handle scoped packages like @scope/package@version
            if missing_pkg.startswith("@"):
                # Scoped package: @scope/package@version -> @scope/package
                parts = missing_pkg.split("@")
                if len(parts) >= 3:  # @scope/package@version
                    pkg_name = "@" + parts[1]  # @scope/package
                else:
                    pkg_name = missing_pkg
            else:
                # Regular package: package@version -> package
                pkg_name = (
                    missing_pkg.split("@")[0] if "@" in missing_pkg else missing_pkg
                )

            script_versions = [
                s for s in script_npx_set if s.startswith(pkg_name + "@")
            ]
            if script_versions:
                version_mismatches.append(
                    f"{pkg_name}: config='{missing_pkg}' script='{script_versions[0]}'"
                )
            else:
                truly_missing.append(missing_pkg)

        error_msg = [
            "❌ Install script does not match template (template is source of truth):",
            "",
        ]
        if version_mismatches:
            error_msg.append("NPX Version mismatches found:")
            error_msg.extend([f"  - {mismatch}" for mismatch in version_mismatches])
            error_msg.append("")
        if truly_missing:
            error_msg.append("NPX Packages missing from install script:")
            error_msg.extend([f"  - {pkg}" for pkg in truly_missing])
            error_msg.append("")

        error_msg.extend(
            [
                "🔧 TO FIX: Update dev_scripts/install_mcp_packages.sh",
                "   - Add missing packages to the npm install -g block",
                "   - Update version numbers to match config exactly",
                "   - Template (mcp_server_template.json) is the source of truth",
            ]
        )

        raise AssertionError("\n".join(error_msg))

    # Check that regular (non-Git) UVX packages from config are in script
    config_uvx_set = set(config_packages["uvx"])
    script_uvx_set = set(script_packages["uvx"])

    # Only check non-Git packages (ones with == version)
    config_regular_uvx = {pkg for pkg in config_uvx_set if "==" in pkg}

    # Also check for packages without versions (potential config errors)
    config_unversioned_uvx = {
        pkg for pkg in config_uvx_set if "==" not in pkg and not pkg.startswith("git+")
    }

    missing_uvx = config_regular_uvx - script_uvx_set

    # Check for unversioned packages that might match versioned ones in script
    unversioned_issues = []
    for unversioned_pkg in config_unversioned_uvx:
        script_versions = [
            s for s in script_uvx_set if s.startswith(unversioned_pkg + "==")
        ]
        if script_versions:
            unversioned_issues.append(
                f"{unversioned_pkg}: config missing version, script has '{script_versions[0]}'"
            )
        else:
            unversioned_issues.append(
                f"{unversioned_pkg}: config missing version and not found in script"
            )

    if missing_uvx or unversioned_issues:
        # Check if it's a version mismatch rather than completely missing
        version_mismatches = []
        truly_missing = []

        for missing_pkg in missing_uvx:
            pkg_name = missing_pkg.split("==")[0]
            script_versions = [
                s for s in script_uvx_set if s.startswith(pkg_name + "==")
            ]
            if script_versions:
                version_mismatches.append(
                    f"{pkg_name}: config='{missing_pkg}' script='{script_versions[0]}'"
                )
            else:
                truly_missing.append(missing_pkg)

        error_msg = [
            "❌ Install script does not match template (template is source of truth):",
            "",
        ]
        if version_mismatches:
            error_msg.append("UVX Version mismatches found:")
            error_msg.extend([f"  - {mismatch}" for mismatch in version_mismatches])
            error_msg.append("")
        if truly_missing:
            error_msg.append("UVX Packages missing from install script:")
            error_msg.extend([f"  - {pkg}" for pkg in truly_missing])
            error_msg.append("")
        if unversioned_issues:
            error_msg.append("UVX Config packages missing version specification:")
            error_msg.extend([f"  - {issue}" for issue in unversioned_issues])
            error_msg.append("")

        error_msg.extend(
            [
                "🔧 TO FIX: Update dev_scripts/install_mcp_packages.sh",
                "   - Add missing packages as 'uv tool install package==version'",
                "   - Update version numbers to match config exactly",
                "   - Fix any unversioned packages in config first",
                "   - Template (mcp_server_template.json) is the source of truth",
            ]
        )

        raise AssertionError("\n".join(error_msg))

    print(
        f"✅ All {len(config_regular_npx)} NPX packages from template are in install script!"
    )
    print(
        f"✅ All {len(config_regular_uvx)} UVX packages from template are in install script!"
    )

    print("✅ Install script matches template (source of truth)!")


if __name__ == "__main__":
    test_package_sync()
