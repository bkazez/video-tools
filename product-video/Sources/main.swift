// product-video -- put a product's frames into a film.
//
//     product-video storyboard.json --frames DIR --out film.mp4 [--audio a.wav]
//                   [--gain-db X] [--width 1920] [--poster-at 4]
//     product-video storyboard.json --check          the storyboard alone
//
// The division of labour, which is the whole reason this exists:
//
//   a FRAME SOURCE, one per product, drives the product through a scripted
//   timeline and writes bare frames -- `%05d.png` of the product and nothing
//   else -- plus `timeline.json` saying what shape it drew, what its window is
//   called, and where each camera move was aiming, since where `autoedit` is on
//   screen is something only the product knows.
//
//   this TOOL, shared, does everything that is film rather than product: the
//   window around it, the camera, the cards and titles and keycaps, the mux, the
//   loudness, the poster. So arc, an iPhone app and a web page come out looking
//   like three films from one house.
//
// The grammar is skills/product-video/reference/storyboard.md. The reference
// frame source is `Arc --movie` in ~/Projects/arc.

import AppKit

let arguments = CommandLine.arguments
func text(_ name: String) -> String? {
    guard let at = arguments.firstIndex(of: name), at + 1 < arguments.count else { return nil }
    return arguments[at + 1]
}
func number(_ name: String, _ fallback: Double) -> Double {
    Double(text(name) ?? "") ?? fallback
}

guard arguments.count > 1, !arguments[1].hasPrefix("-") else {
    fail("usage: product-video storyboard.json --frames DIR --out film.mp4 [--audio a.wav]")
}
let storyboard = Storyboard(path: arguments[1])
storyboard.checkBeat()

if arguments.contains("--check") {
    print("the storyboard reads, and every title lands on the beat")
    exit(0)
}

guard let frames = text("--frames"), let out = text("--out") else {
    fail("--frames DIR and --out FILM.mp4 are both needed")
}
let timeline = Timeline(path: "\(frames)/timeline.json")
let titles = storyboard.titles()
let bar = timeline.title == nil ? 0 : Film.barHeight
let canvas = NSRect(x: 0, y: 0, width: timeline.width, height: timeline.height + bar)

// MARK: the frames

let dressed = "\(frames)/dressed"
try? FileManager.default.createDirectory(atPath: dressed, withIntermediateDirectories: true)

/// How far into a camera move we are, and how far it is going.
func camera(at time: Double) -> (scale: CGFloat, target: CGFloat, focus: CGPoint)? {
    var state: (scale: CGFloat, target: CGFloat, focus: CGPoint)?
    for move in timeline.camera where move.at <= time {
        let done = min(1, max(0, (time - move.at) / max(move.seconds, 0.001)))
        // The same ease the frame source uses for its own moves.
        let eased = done < 0.5 ? 2 * done * done : 1 - pow(-2 * done + 2, 2) / 2
        let from = state?.scale ?? 1
        state = (from * pow(move.to / from, eased), move.to, move.focus)
    }
    return state
}

for index in 0..<timeline.frames {
    let now = Double(index) / timeline.fps
    let name = String(format: "%05d.png", index)
    guard let source = NSImage(contentsOfFile: "\(frames)/\(name)") else {
        fail("no frame \(name) in \(frames)")
    }
    let scale = source.size.width / timeline.width      // the master's resolution

    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: Int(canvas.width * scale), pixelsHigh: Int(canvas.height * scale),
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0),
        let context = NSGraphicsContext(bitmapImageRep: rep) else {
        fail("could not make a canvas for frame \(index)")
    }
    rep.size = canvas.size

    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context

    // The window and the product travel together under the camera; the words do
    // not, or they would fly off with the picture and stop being readable.
    let lens = camera(at: now)
    if let lens, lens.scale > 1.0001 {
        context.saveGraphicsState()
        Film.lens(scale: lens.scale, target: lens.target,
                  focus: CGPoint(x: lens.focus.x, y: canvas.height - bar - lens.focus.y),
                  in: canvas).concat()
    }
    if let title = timeline.title { Film.drawChrome(title, in: canvas) }
    source.draw(in: NSRect(x: 0, y: 0, width: timeline.width, height: timeline.height))
    if let lens, lens.scale > 1.0001 { context.restoreGraphicsState() }

    for card in titles.cards where now >= card.start && now < card.end {
        Film.drawCard(card.text, then: card.then, start: card.start, end: card.end,
                      now: now, in: canvas)
    }
    for step in titles.steps where now >= step.start && now < step.end {
        Film.drawStep(step.text, start: step.start, end: step.end, now: now, in: canvas)
    }
    // A keycap stands for two thirds of a second and goes out over the last
    // fifth, which is about as long as a key feels pressed. It sits where a
    // title sits, and drops below one that is still up rather than landing in
    // the middle of the words.
    if let key = titles.keys.last(where: { now >= $0.at && now < $0.at + 0.7 }),
       !titles.cards.contains(where: { now >= $0.start && now < $0.end }) {
        let underTitle = titles.steps.contains { now >= $0.start && now < $0.end } ? 76.0 : 0.0
        Film.drawKeycap(key.cap, fade: min(1, (0.7 - (now - key.at)) / 0.2),
                        under: underTitle, in: canvas)
    }
    NSGraphicsContext.restoreGraphicsState()

    guard let png = rep.representation(using: .png, properties: [:]),
          (try? png.write(to: URL(fileURLWithPath: "\(dressed)/\(name)"))) != nil else {
        fail("could not write \(dressed)/\(name)")
    }
}

// MARK: the film

@discardableResult
func run(_ tool: String, _ argv: [String]) -> String {
    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    task.arguments = [tool] + argv
    let pipe = Pipe(), errors = Pipe()
    task.standardOutput = pipe
    task.standardError = errors
    try? task.run()
    let output = pipe.fileHandleForReading.readDataToEndOfFile()
    let complaint = errors.fileHandleForReading.readDataToEndOfFile()
    task.waitUntilExit()
    if task.terminationStatus != 0 {
        fail("\(tool) failed:\n" + (String(data: complaint, encoding: .utf8) ?? ""))
    }
    return String(data: output, encoding: .utf8) ?? ""
}

let width = Int(number("--width", 1920))
var encode = ["-y", "-framerate", "\(timeline.fps)", "-i", "\(dressed)/%05d.png"]
if let audio = text("--audio") { encode += ["-i", audio] }
encode += ["-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
           "-vf", "scale=\(width):-2"]
if text("--audio") != nil {
    let gain = number("--gain-db", 0)
    if abs(gain) > 0.01 { encode += ["-af", String(format: "volume=%.2fdB", gain)] }
    encode += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
}
encode += ["-movflags", "+faststart", out]
run("ffmpeg", encode)

let poster = (out as NSString).deletingPathExtension + "-poster.jpg"
// Inside the film: a poster asked for at the fourth second of a two second film
// is an ffmpeg run that writes nothing and says so in forty lines.
let posterAt = min(number("--poster-at", 3),
                   Double(timeline.frames - 1) / timeline.fps)
run("ffmpeg", ["-y", "-ss", "\(max(posterAt, 0))", "-i", out,
               "-frames:v", "1", "-q:v", "3", poster])

let size = ((try? FileManager.default.attributesOfItem(atPath: out))?[.size] as? Int) ?? 0
print(String(format: "%@ (%.1f MB), %@", out, Double(size) / 1e6,
             (poster as NSString).lastPathComponent))
