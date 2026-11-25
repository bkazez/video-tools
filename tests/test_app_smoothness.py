#!/usr/bin/env python3
"""app-smoothness finds the demo test's target the way Xcode compiles it, and names the
test's last action before each stutter.

    python3 tests/test_app_smoothness.py
"""
import importlib.machinery
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent.parent
loader = importlib.machinery.SourceFileLoader("app_smoothness", str(HERE / "bin" / "app-smoothness"))
spec = importlib.util.spec_from_loader("app_smoothness", loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)

failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'' if ok else '  -- ' + detail}")
    if not ok:
        failures.append(label)


def project(folder, objects):
    path = folder / "App.xcodeproj"
    path.mkdir()
    (path / "project.pbxproj").write_text(json.dumps({"objects": objects}))
    return path


steps = [(100.0, "Set Up"), (100.5, "Launch com.example.App"), (103.0, 'Tap "open" Button'),
         (103.1, "Wait for com.example.App to idle"), (103.2, "Synthesize event"),
         (104.0, 'Waiting 30.0s for "card" ScrollView to exist')]
said = app.step_at(steps, 100.0, 3.8)
check("a stutter is named by the action before it, not the wait after", said.endswith('Tap "open" Button'), said)
check("with how long after it", said.strip().startswith("0.80 s after"), said)
check("one before any action says so", app.step_at(steps, 100.0, 0.2) == "before the test's first action")

with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    listed = tmp / "listed"
    listed.mkdir()
    test = listed / "AppUITests" / app.TEST_FILE
    made = project(listed, {
        "ref": {"isa": "PBXFileReference", "path": app.TEST_FILE},
        "build": {"isa": "PBXBuildFile", "fileRef": "ref"},
        "sources": {"isa": "PBXSourcesBuildPhase", "files": ["build"]},
        "other": {"isa": "PBXSourcesBuildPhase", "files": []},
        "app": {"isa": "PBXNativeTarget", "name": "App", "buildPhases": ["other"]},
        "ui": {"isa": "PBXNativeTarget", "name": "AppUITests", "buildPhases": ["sources"]}})
    check("a listed file's target", app.target_for(made, test) == "AppUITests")

    synced = tmp / "synced"
    synced.mkdir()
    test = synced / "UITests" / app.TEST_FILE
    made = project(synced, {
        "group": {"isa": "PBXFileSystemSynchronizedRootGroup", "path": "UITests"},
        "app": {"isa": "PBXNativeTarget", "name": "App", "buildPhases": []},
        "ui": {"isa": "PBXNativeTarget", "name": "AppUITests", "fileSystemSynchronizedGroups": ["group"]}})
    check("a synchronized folder's target", app.target_for(made, test) == "AppUITests")

    schemes = made / "xcshareddata" / "xcschemes"
    schemes.mkdir(parents=True)
    (schemes / "Other.xcscheme").write_text('<TestAction></TestAction>')
    (schemes / "Tests.xcscheme").write_text('<TestAction><BuildableReference BlueprintName = "AppUITests">'
                                            '</TestAction>')
    check("the shared scheme that tests the target", app.scheme_for(made, "AppUITests") == "Tests")
    check("else the project's name", app.scheme_for(made, "Elsewhere") == "App")

print("\nall passed" if not failures else f"\n{len(failures)} failed")
sys.exit(1 if failures else 0)
