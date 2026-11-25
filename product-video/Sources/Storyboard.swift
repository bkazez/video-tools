// The storyboard: what the film says, and when.
//
// Read by this tool and by whatever draws the product. The grammar is
// skills/product-video/reference/storyboard.md; the only parts here are the ones
// a compositor needs -- the words, their moments, and the beat they land on.

import AppKit

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
        // An empty list is a film with no words; no list at all is a typo.
        guard let listed = board["events"] as? [[String: Any]] else { fail("the storyboard has no events") }
        events = listed.sorted { (Storyboard.number($0["at"]) ?? 0) < (Storyboard.number($1["at"]) ?? 0) }
    }

    static func colour(_ hex: String) -> NSColor {
        guard hex.hasPrefix("#"), hex.count == 7, let rgb = Int(hex.dropFirst(), radix: 16) else {
            fail("background is \(hex); it wants #RRGGBB")
        }
        return NSColor(srgbRed: CGFloat(rgb >> 16 & 255) / 255, green: CGFloat(rgb >> 8 & 255) / 255,
                       blue: CGFloat(rgb & 255) / 255, alpha: 1)
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
        /// How much of the canvas's height a device's bezel stands in. Room for
        /// titles above and below it by default; a film with no words gives the
        /// phone nearly all of it.
        let deviceFill: CGFloat
        /// What the canvas is behind the product where there is no room footage.
        let background: NSColor?
        /// Whether the cards, steps and keycaps are drawn.
        let words: Bool
        /// Whether the storyboard's camera moves are played.
        let camera: Bool
    }

    /// The cuts every film of a device has, by name, so every app's films come
    /// out the same: `wide` 16:9 and `feed` 4:5 for a feed, `vertical` 9:16 for
    /// a reel, `phone` the bezel alone on black for a web page that stands it
    /// beside its own words (no titles, no camera), and `preview` the screen
    /// alone for the App Store. A storyboard's block of the same name overrides
    /// any of their keys. Points, at the storyboard's `scale`.
    static let deviceCuts: [String: [String: Any]] = [
        "wide": ["canvas": ["width": 960, "height": 540]],
        "feed": ["canvas": ["width": 540, "height": 675]],
        "vertical": ["canvas": ["width": 540, "height": 960]],
        "phone": ["canvas": "device", "device_fill": 0.98, "background": "#000000", "words": false, "camera": false],
        "preview": ["chrome": false, "canvas": false, "words": false, "camera": false],
    ]

    /// A variant is the same film redrawn in another shape rather than cropped
    /// out of the wide one: a built-in cut above, or any block the storyboard
    /// names. A variant's `canvas: false` means no room around the product,
    /// even when the wide film has one; `canvas: "device"` is the bezel's own
    /// shape with `device_fill` of margin, and `words` and `camera` false leave
    /// out the titles and the camera moves.
    func geometry(variant: String?) -> Geometry {
        let device = (board["chrome"]).flatMap { Storyboard.chrome($0) }.map { $0 != "macos" } ?? false
        let block = variant.map { name in
            (device ? Storyboard.deviceCuts[name] ?? [:] : [:])
                .merging(board[name] as? [String: Any] ?? [:]) { _, own in own }
        } ?? [:]
        func value(_ key: String) -> Double? {
            Storyboard.number(block[key]) ?? Storyboard.number(board[key])
        }
        let size = CGSize(width: value("width") ?? 0, height: value("height") ?? 0)
        let chrome = (block["chrome"] ?? board["chrome"]).flatMap { Storyboard.chrome($0) }
        let fill = CGFloat(value("device_fill") ?? 0.72)
        func canvasSize() -> CGSize? {
            let raw = block.keys.contains("canvas") ? block["canvas"] : board["canvas"]
            if raw as? String == "device" {
                guard let chrome, chrome != "macos" else { fail("canvas \"device\" needs a device chrome") }
                let device = Film.device(chrome, for: size)
                let points = size.height / device.screen.height / fill
                return CGSize(width: (device.size.width * points).rounded(), height: (device.size.height * points).rounded())
            }
            guard let raw = raw as? [String: Any],
                  let wide = Storyboard.number(raw["width"]),
                  let tall = Storyboard.number(raw["height"]) else { return nil }
            return CGSize(width: wide, height: tall)
        }
        return Geometry(
            size: size,
            canvas: canvasSize(),
            scale: CGFloat(value("scale") ?? 1),
            chrome: chrome,
            deviceFill: fill,
            background: ((block["background"] ?? board["background"]) as? String).map(Storyboard.colour),
            words: block["words"] as? Bool ?? true,
            camera: block["camera"] as? Bool ?? true)
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
            // A keycap is for a key the viewer should feel their own hand press.
            // Not every keystroke the script needs is one of those -- the ones
            // that set something up read as noise beside the ones that are the
            // point -- so an event can say `"keycap": false` and stay silent.
            if let step = (event["do"] as? String)?.trimmingCharacters(in: .whitespaces),
               step.hasPrefix("key:"), event["keycap"] as? Bool ?? true {
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
    /// How much of the product's own height, from the top, a title may stand
    /// in when the product fills the picture. Nothing, and the words go over
    /// the middle. A phone app whose middle is its own headline says 0.08 or
    /// so: the status bar's worth.
    let titleBand: CGFloat?
    /// `"macos"`, or a device `bin/device-frame` knows. A frame source that says
    /// nothing but gives a window title still gets the macOS bar, which is what
    /// every one of them meant before this key existed.
    let chrome: String?
    /// How many pixels the frame source drew per point. Inferred from the frames
    /// themselves where it is not said, which is what it always was.
    let scale: CGFloat?
    let camera: [(at: Double, to: CGFloat, seconds: Double, focus: CGPoint)]
    /// Spans the frame source scripted, as the camera is, which the smoothness
    /// check is not to judge: a UI-test film's app animation starting from a tap.
    let skip: [(from: Double, to: Double)]

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
        titleBand = Storyboard.number(body["titleBand"]).map { CGFloat($0) }
        skip = (body["skip"] as? [[Any]] ?? []).compactMap { span in
            guard span.count == 2, let from = Storyboard.number(span[0]), let to = Storyboard.number(span[1]) else { return nil }
            return (from, to)
        }
        camera = (body["camera"] as? [[String: Any]] ?? []).map {
            (Storyboard.number($0["at"]) ?? 0,
             CGFloat(Storyboard.number($0["to"]) ?? 1),
             Storyboard.number($0["seconds"]) ?? 1,
             CGPoint(x: Storyboard.number($0["x"]) ?? 0, y: Storyboard.number($0["y"]) ?? 0))
        }
    }
}

func fail(_ text: String, code: Int32 = 2) -> Never {
    FileHandle.standardError.write(("product-video: " + text + "\n").data(using: .utf8)!)
    exit(code)
}

/// The exit code of a film refused as jerky: the recording stuttered, so a fresh one may
/// not (bin/film-until-smooth records again on it). Every other failure is exit 2.
let jerky: Int32 = 3
