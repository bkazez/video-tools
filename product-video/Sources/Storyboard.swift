// The storyboard: what the film says, and when.
//
// Read by this tool and by whatever draws the product. The grammar is
// skills/product-video/reference/storyboard.md; the only parts here are the ones
// a compositor needs -- the words, their moments, and the beat they land on.

import Foundation

struct Storyboard {
    let seconds: Double
    let fps: Double
    let beat: Double?
    let subdivide: Double
    let events: [[String: Any]]
    private let board: [String: Any]

    init(path: String) {
        guard let data = FileManager.default.contents(atPath: path),
              let board = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            fail("could not read the storyboard \(path)")
        }
        self.board = board
        seconds = Storyboard.number(board["seconds"]) ?? 30
        fps = Storyboard.number(board["fps"]) ?? 30
        beat = Storyboard.number(board["beat"])
        subdivide = max(Storyboard.number(board["subdivide"]) ?? 1, 1)
        events = (board["events"] as? [[String: Any]] ?? [])
            .sorted { (Storyboard.number($0["at"]) ?? 0) < (Storyboard.number($1["at"]) ?? 0) }
        guard !events.isEmpty else { fail("the storyboard has no events") }
    }

    static func number(_ raw: Any?) -> Double? { (raw as? NSNumber)?.doubleValue }

    /// The shape of the film, in points, before the master's supersampling.
    ///
    /// `size` is the product's own drawing area and `canvas` is the frame the
    /// film is cut in. They are the same thing only for a product that fills the
    /// picture. A phone does not: it stands in a room, and the room is the rest
    /// of the canvas.
    struct Geometry {
        let size: CGSize
        let canvas: CGSize?
        let scale: CGFloat
        let chrome: String?
    }

    /// A phone gets the same film redrawn in the `vertical` block's shape rather
    /// than cropped out of the wide one, so say which one you are rendering.
    func geometry(vertical: Bool) -> Geometry {
        let block = (vertical ? board["vertical"] as? [String: Any] : nil) ?? [:]
        func value(_ key: String) -> Double? {
            Storyboard.number(block[key]) ?? Storyboard.number(board[key])
        }
        func canvasSize() -> CGSize? {
            guard let raw = (block["canvas"] ?? board["canvas"]) as? [String: Any],
                  let wide = Storyboard.number(raw["width"]),
                  let tall = Storyboard.number(raw["height"]) else { return nil }
            return CGSize(width: wide, height: tall)
        }
        return Geometry(
            size: CGSize(width: value("width") ?? 0, height: value("height") ?? 0),
            canvas: canvasSize(),
            scale: CGFloat(value("scale") ?? 1),
            chrome: (block["chrome"] ?? board["chrome"]).flatMap { Storyboard.chrome($0) })
    }

    /// `chrome` was a bool while there was only one thing it could mean. It now
    /// names which window or which bezel, and `true` still means the platform's
    /// own window.
    static func chrome(_ raw: Any) -> String? {
        if let name = raw as? String { return name }
        if let on = raw as? Bool { return on ? "macos" : nil }
        return nil
    }

    /// Every event a viewer can hear or read has to land on the beat.
    ///
    /// A film of an interface is watched the way music is listened to: what makes
    /// twenty seconds feel fast is not how much happens but how regularly it
    /// happens, and a title that arrives 0.3 s late reads as a stumble even
    /// though nobody could say what changed.
    ///
    /// The mechanics in between -- a pointer gliding, a button going down, the
    /// release before a Return -- are free, because they are how a beat is
    /// reached rather than the beat itself.
    func checkBeat() {
        guard let beat, beat > 0 else { return }
        let grid = beat / subdivide
        let slack = 0.5 / fps                    // half a frame; the grid is in time
        for event in events {
            let at = Storyboard.number(event["at"]) ?? 0
            let key = (event["do"] as? String)?.trimmingCharacters(in: .whitespaces) ?? ""
            // `scene` is a cut to somewhere else, which is as loud as a title.
            let rhythmic = event["card"] != nil || event["step"] != nil
                || event["play"] != nil || event["zoom"] != nil || event["camera"] != nil
                || event["scene"] != nil || key.hasPrefix("key:")
            guard rhythmic else { continue }
            let beats = (at / grid).rounded()
            if abs(at - beats * grid) > slack {
                let what = key.isEmpty
                    ? (event.keys.first { $0 != "at" && $0 != "seconds" } ?? "?") : key
                fail(String(format:
                    "%@ is at %.2fs, off the %.3fs grid -- the nearest are %.2f and %.2f",
                    what, at, grid, (beats - 1) * grid, (beats + 1) * grid))
            }
        }
    }

    /// The words, and the keys, in the order they appear. Everything else in the
    /// storyboard is the frame source's business.
    struct Titles {
        var cards: [(text: String, then: (text: String, at: Double)?, start: Double, end: Double)] = []
        var steps: [(text: String, start: Double, end: Double)] = []
        var keys: [(cap: String, at: Double)] = []
    }

    func titles() -> Titles {
        var found = Titles()
        for event in events {
            let at = Storyboard.number(event["at"]) ?? 0
            let seconds = max(Storyboard.number(event["seconds"]) ?? 0, 0.001)
            if let text = event["card"] as? String {
                var second: (text: String, at: Double)?
                if let follow = event["then"] as? [String: Any],
                   let words = follow["text"] as? String {
                    second = (words, at + (Storyboard.number(follow["at"]) ?? 0))
                }
                found.cards.append((text, second, at, at + seconds))
            }
            if let text = event["step"] as? String {
                found.steps.append((text, at, at + seconds))
            }
            if let step = (event["do"] as? String)?.trimmingCharacters(in: .whitespaces),
               step.hasPrefix("key:") {
                found.keys.append((keycap(String(step.dropFirst(4))), at))
            }
        }
        return found
    }

    /// What a keystroke looks like when it is drawn rather than typed. The script
    /// writes `up`, `return`, `a+shift`; a viewer recognises the glyphs on their
    /// own keyboard.
    private func keycap(_ spec: String) -> String {
        let parts = spec.trimmingCharacters(in: .whitespaces).components(separatedBy: "+")
        let symbols: [String: String] = [
            "up": "\u{2191}", "down": "\u{2193}", "left": "\u{2190}", "right": "\u{2192}",
            "return": "\u{21A9}", "space": "space", "escape": "esc", "tab": "tab",
            "backspace": "\u{232B}", "delete": "\u{2326}", "backslash": "\\",
            "bracketleft": "[", "bracketright": "]",
        ]
        var cap = symbols[parts[0].lowercased()] ?? parts[0].uppercased()
        for modifier in parts.dropFirst() {
            switch modifier.lowercased() {
            case "cmd", "command": cap = "\u{2318}" + cap
            case "shift": cap = "\u{21E7}" + cap
            case "opt", "option", "alt": cap = "\u{2325}" + cap
            case "ctrl", "control": cap = "\u{2303}" + cap
            default: break
            }
        }
        return cap
    }
}

/// What the frame source hands over with its frames: the shape it drew, the
/// window title it would have carried, and every camera move with its focus
/// already resolved -- because where `autoedit` or `head@123.8` is on screen is
/// something only the product knows.
struct Timeline {
    let fps: Double
    let frames: Int
    let width: CGFloat
    let height: CGFloat
    let title: String?
    /// The film's frame, when it is bigger than the product. A phone stands in a
    /// room and the room is the rest of the canvas; a take stack fills its own
    /// window and has no canvas at all.
    let canvas: CGSize?
    /// `"macos"`, or a device `bin/device-frame` knows. A frame source that says
    /// nothing but gives a window title still gets the macOS bar, which is what
    /// every one of them meant before this key existed.
    let chrome: String?
    /// How many pixels the frame source drew per point. Inferred from the frames
    /// themselves where it is not said, which is what it always was.
    let scale: CGFloat?
    let camera: [(at: Double, to: CGFloat, seconds: Double, focus: CGPoint)]

    init(path: String) {
        guard let data = FileManager.default.contents(atPath: path),
              let body = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            fail("could not read \(path); the frame source has to write one")
        }
        fps = Storyboard.number(body["fps"]) ?? 30
        frames = Int(Storyboard.number(body["frames"]) ?? 0)
        width = CGFloat(Storyboard.number(body["width"]) ?? 0)
        height = CGFloat(Storyboard.number(body["height"]) ?? 0)
        title = body["title"] as? String
        scale = Storyboard.number(body["scale"]).map { CGFloat($0) }
        if let raw = body["canvas"] as? [String: Any],
           let wide = Storyboard.number(raw["width"]),
           let tall = Storyboard.number(raw["height"]) {
            canvas = CGSize(width: wide, height: tall)
        } else {
            canvas = nil
        }
        chrome = body["chrome"].flatMap { Storyboard.chrome($0) } ?? (title == nil ? nil : "macos")
        camera = (body["camera"] as? [[String: Any]] ?? []).map {
            (Storyboard.number($0["at"]) ?? 0,
             CGFloat(Storyboard.number($0["to"]) ?? 1),
             Storyboard.number($0["seconds"]) ?? 1,
             CGPoint(x: Storyboard.number($0["x"]) ?? 0, y: Storyboard.number($0["y"]) ?? 0))
        }
    }
}

func fail(_ text: String) -> Never {
    FileHandle.standardError.write(("product-video: " + text + "\n").data(using: .utf8)!)
    exit(2)
}
