// Everything a product film wears: the window around it, the camera that flies
// into it, and the words on top.
//
// None of this knows what the product is. It is given a picture of one and a
// storyboard, and it does the same things to every product -- which is the point:
// the take stack, an iPhone app and a web page should come out looking like three
// films from one house rather than three films.
//
// Lifted from arc's own `Movie.swift`, where it was written first and where the
// typography was settled. Kept in AppKit rather than rebuilt on a portable
// drawing library on purpose: the look IS this text rendering, and a second
// implementation would drift on the first title.

import AppKit

enum Film {
    /// How tall a macOS title bar is, and therefore how far down the app starts.
    static let barHeight: CGFloat = 30

    // MARK: the window

    /// A macOS title bar: the three lights, and the window's own title. The
    /// interior is the app; this strip is the film's, and it is here because a
    /// rectangle of interface with nothing around it reads as a diagram rather
    /// than as software somebody is using.
    static func drawChrome(_ title: String, in canvas: NSRect) {
        let bar = NSRect(x: 0, y: canvas.height - barHeight, width: canvas.width, height: barHeight)
        NSColor(calibratedWhite: 0.16, alpha: 1).setFill()
        bar.fill()
        NSColor(calibratedWhite: 0.09, alpha: 1).setFill()
        NSRect(x: 0, y: bar.minY, width: canvas.width, height: 1).fill()

        let lights: [NSColor] = [NSColor(calibratedRed: 1.0, green: 0.37, blue: 0.35, alpha: 1),
                                 NSColor(calibratedRed: 1.0, green: 0.74, blue: 0.19, alpha: 1),
                                 NSColor(calibratedRed: 0.16, green: 0.79, blue: 0.25, alpha: 1)]
        for (index, colour) in lights.enumerated() {
            colour.setFill()
            let dot = NSRect(x: 14 + CGFloat(index) * 20, y: bar.midY - 6, width: 12, height: 12)
            NSBezierPath(ovalIn: dot).fill()
        }

        let drawn = NSAttributedString(string: title, attributes: [
            .font: NSFont.systemFont(ofSize: 13, weight: .semibold),
            .foregroundColor: NSColor(calibratedWhite: 0.72, alpha: 1),
        ])
        let size = drawn.size()
        drawn.draw(at: NSPoint(x: (canvas.width - size.width) / 2, y: bar.midY - size.height / 2))
    }

    // MARK: pictures

    /// A picture whose size is its pixels.
    ///
    /// `NSImage.size` is in points, and a PNG carrying a dpi says its points are
    /// a third of its pixels -- which is exactly what Apple's own device bezels
    /// do. Everything here measures in the master's pixels, so every picture is
    /// read that way and none of them are trusted to agree about dpi.
    static func picture(_ path: String) -> NSImage? {
        guard let image = NSImage(contentsOfFile: path),
              let rep = image.representations.first else { return nil }
        image.size = NSSize(width: rep.pixelsWide, height: rep.pixelsHigh)
        return image
    }

    // MARK: the device

    /// A bezel, and where the screen sits inside it. Both come from
    /// `bin/device-frame`, which is the one table: the still pipeline reads the
    /// same row, so a framed screenshot and a frame of the film cannot disagree
    /// about where the glass is.
    struct Device {
        let bezel: NSImage
        let screen: NSRect          // within the bezel image, top-left origin
        let radius: CGFloat
        var size: NSSize { bezel.size }
    }

    /// How much of the canvas's height the bezel stands in.
    ///
    /// High enough that the phone is the subject, low enough that a band of room
    /// is left above and below it -- because a device's whole screen is usually
    /// words, and a title centred over the middle of the frame would land on top
    /// of them. The room is where the film's own words go.
    static let deviceFill: CGFloat = 0.72

    static func device(_ name: String) -> Device {
        guard let home = ProcessInfo.processInfo.environment["PRODUCT_VIDEO_HOME"] else {
            fail("PRODUCT_VIDEO_HOME is unset; run this through bin/product-video")
        }
        let tool = "\(home)/bin/device-frame"
        guard FileManager.default.isExecutableFile(atPath: tool) else {
            fail("no \(tool); it is what knows where each bezel's screen hole is")
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: tool)
        task.arguments = [name, "--json"]
        let pipe = Pipe(), errors = Pipe()
        task.standardOutput = pipe
        task.standardError = errors
        try? task.run()
        let said = pipe.fileHandleForReading.readDataToEndOfFile()
        let complaint = errors.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()
        guard task.terminationStatus == 0,
              let row = (try? JSONSerialization.jsonObject(with: said)) as? [String: Any],
              let path = row["path"] as? String, let bezel = Film.picture(path) else {
            fail("device-frame could not give a bezel for \(name): "
                 + (String(data: complaint, encoding: .utf8) ?? ""))
        }
        func at(_ key: String) -> CGFloat { CGFloat(Storyboard.number(row[key]) ?? 0) }
        return Device(bezel: bezel,
                      screen: NSRect(x: at("screen_x"), y: at("screen_y"),
                                     width: at("screen_width"), height: at("screen_height")),
                      radius: at("radius"))
    }

    /// Where the bezel stands in the canvas, and where its glass is -- the rect
    /// the product gets drawn into. Centred, because a phone off to one side
    /// reads as a layout and a phone in the middle reads as the subject.
    static func stand(_ device: Device, in canvas: NSRect) -> (bezel: NSRect, screen: NSRect) {
        let scale = canvas.height * deviceFill / device.size.height
        let bezel = NSRect(x: canvas.midX - device.size.width * scale / 2,
                           y: canvas.midY - device.size.height * scale / 2,
                           width: device.size.width * scale,
                           height: device.size.height * scale)
        // The table gives the hole measured from the top of the bezel; a canvas
        // counts up from the bottom.
        let screen = NSRect(
            x: bezel.minX + device.screen.minX * scale,
            y: bezel.maxY - (device.screen.minY + device.screen.height) * scale,
            width: device.screen.width * scale,
            height: device.screen.height * scale)
        return (bezel, screen)
    }

    /// The product on the glass, then the bezel over it. The product is clipped
    /// to the screen's own radius first: a screenshot is a square rectangle and
    /// a screen is not, so without the clip its corners sit in the cutout as
    /// four dark squares behind the titanium.
    static func drawDevice(_ device: Device, product: NSImage,
                           bezel: NSRect, screen: NSRect) {
        NSGraphicsContext.saveGraphicsState()
        let radius = device.radius * bezel.height / device.size.height
        NSBezierPath(roundedRect: screen, xRadius: radius, yRadius: radius).addClip()
        product.draw(in: screen)
        NSGraphicsContext.restoreGraphicsState()
        device.bezel.draw(in: bezel)
    }

    // MARK: the room it is standing in

    /// Footage of wherever the product is being used, behind it. Dimmed a
    /// little, because a room at full brightness competes with the screen that
    /// is the point of the film, and the screen has to win.
    static func drawBackdrop(_ image: NSImage, in canvas: NSRect) {
        image.draw(in: canvas)
        NSColor.black.withAlphaComponent(0.18).setFill()
        canvas.fill()
    }

    // MARK: the camera

    /// The transform that magnifies the finished picture about `focus`, bringing
    /// it toward the middle of the frame as it goes -- as far as it can without
    /// showing what is outside the window. A button 50 points from the corner
    /// cannot reach the middle at 3x, and a frame half full of black is worse
    /// than one where the subject sits off centre.
    static func lens(scale: CGFloat, target: CGFloat, focus: CGPoint,
                     in canvas: NSRect) -> NSAffineTransform {
        let toward = (scale - 1) / max(target - 1, 0.0001)
        let room = scale - 1
        let pan = CGPoint(
            x: min(max((canvas.midX - focus.x) * toward, room * (focus.x - canvas.width)),
                   room * focus.x),
            y: min(max((canvas.midY - focus.y) * toward, room * (focus.y - canvas.height)),
                   room * focus.y))
        let move = NSAffineTransform()
        move.translateX(by: pan.x, yBy: pan.y)
        move.translateX(by: focus.x, yBy: focus.y)
        move.scaleX(by: scale, yBy: scale)
        move.translateX(by: -focus.x, yBy: -focus.y)
        return move
    }

    // MARK: the words

    /// Where the product is, when a title has to stay off it. A product that
    /// fills the picture leaves this nothing and the words go in the middle, as
    /// they always have.
    static var keepClear: NSRect?

    /// Titles are centred, and the keys pressed after one appear in the same
    /// place, so a viewer's eye never leaves the middle of the frame.
    ///
    /// Unless the middle of the frame is a screen with words on it. Then the
    /// title takes the taller of the two bands the product leaves free, because
    /// two sentences in one place are worse than either alone -- and the eye
    /// still has somewhere settled to be, since every title in a film picks the
    /// same band.
    static func titleBaseline(in bounds: NSRect, height: CGFloat) -> CGFloat {
        guard let band = clearBand(in: bounds, height: height) else {
            return (bounds.height - height) / 2
        }
        return band.midY - height / 2
    }

    /// The band a title stands in, or nothing if the product leaves no room for
    /// one and the words have to go over it after all.
    static func clearBand(in bounds: NSRect, height: CGFloat) -> NSRect? {
        guard let product = keepClear else { return nil }
        let below = NSRect(x: 0, y: 0, width: bounds.width, height: max(product.minY, 0))
        let above = NSRect(x: 0, y: product.maxY, width: bounds.width,
                           height: max(bounds.height - product.maxY, 0))
        let roomier = below.height >= above.height ? below : above
        return roomier.height >= height + 24 ? roomier : nil
    }

    /// The dark the words are read against.
    ///
    /// Over the whole frame when the words are over the whole frame. When they
    /// have a band of their own, only that band, fading out towards the product
    /// so there is no edge -- a film about light should not black out the room
    /// it is measuring every time it says something.
    static func scrim(_ alpha: Double, over bounds: NSRect, height: CGFloat) {
        guard let band = clearBand(in: bounds, height: height) else {
            NSColor.black.withAlphaComponent(alpha).setFill()
            bounds.fill()
            return
        }
        let solid = NSColor.black.withAlphaComponent(alpha)
        let gone = NSColor.black.withAlphaComponent(0)
        let atBottom = band.minY < bounds.midY
        NSGradient(starting: atBottom ? solid : gone, ending: atBottom ? gone : solid)?
            .draw(in: band, angle: 90)
    }

    /// A title does not fade up, it lands: opaque almost at once, and a fraction
    /// over size for a moment so it arrives with a knock. Linear fades read as
    /// hesitation, and the beat is what this kind of film is built on.
    ///
    /// `handingOver` is set when the next words start the instant these ones
    /// end. Then there is no fade out at all: one set of words gives way to the
    /// next in a single move. Fading one out and the next one in reads as two
    /// beats where the film means one, which is most of what "too much fading"
    /// turns out to be.
    static func pop(_ start: Double, _ end: Double, now at: Double,
                    handingOver: Bool = false) -> (fade: Double, scale: Double) {
        if at >= end { return (0, 1) }
        let since = at - start
        let out = handingOver ? 1 : (end - at) / 0.12
        let fade = min(1, min(since / 0.07, out))
        let settle = min(1, since / 0.16)
        let eased = 1 - pow(1 - settle, 3)
        return (fade, 1.10 - 0.10 * eased)
    }

    static func drawStep(_ text: String, start: Double, end: Double, now at: Double,
                         handingOver: Bool = false, in bounds: NSRect) {
        let (alpha, scale) = pop(start, end, now: at, handingOver: handingOver)
        guard alpha > 0.01 else { return }
        let drawn = line(text, size: 52 * scale, alpha: alpha, in: bounds)
        scrim(0.5 * alpha, over: bounds, height: drawn.height)
        place(drawn.text, in: bounds,
              top: titleBaseline(in: bounds, height: drawn.height) + drawn.height)
    }

    static func drawCard(_ text: String, then second: (text: String, at: Double)?,
                         start: Double, end: Double, now at: Double,
                         handingOver: Bool = false, in bounds: NSRect) {
        let (alpha, scale) = pop(start, end, now: at, handingOver: handingOver)
        guard alpha > 0.01 else { return }
        NSColor.black.withAlphaComponent(0.85 * alpha).setFill()
        bounds.fill()
        // A card takes the whole frame down to almost nothing, so there is
        // nothing left to read behind it and nothing to stay clear of. It goes
        // in the middle, where a film opens.
        let product = keepClear
        keepClear = nil
        defer { keepClear = product }

        guard let second else {
            draw(text, size: 50 * scale, alpha: alpha, in: bounds)
            return
        }
        // Two lines, one block: the first sits where it would sit if it were
        // alone in a block of two, and the second lands under it when its moment
        // comes -- so nothing jumps.
        let (below, belowScale) = pop(second.at, end, now: at, handingOver: handingOver)
        let gap: CGFloat = 18
        let first = line(text, size: 50 * scale, alpha: alpha, in: bounds)
        let follow = line(second.text, size: 50 * belowScale,
                          alpha: at >= second.at ? below : 0, in: bounds)
        let total = first.height + gap + follow.height
        let top = titleBaseline(in: bounds, height: total) + total
        place(first.text, in: bounds, top: top)
        if at >= second.at { place(follow.text, in: bounds, top: top - first.height - gap) }
    }

    /// `under` pushes the cap below a title that is still on screen. They share
    /// a place on purpose -- the eye is already there -- but a key pressed while
    /// a title is up would otherwise land in the middle of the words.
    static func drawKeycap(_ text: String, fade: Double, under title: CGFloat = 0,
                           in bounds: NSRect) {
        guard fade > 0.01 else { return }
        let drawn = NSAttributedString(string: text, attributes: [
            .font: NSFont.systemFont(ofSize: 30, weight: .semibold),
            .foregroundColor: NSColor.white.withAlphaComponent(0.95 * fade),
        ])
        let size = drawn.size()
        let box = NSRect(x: (bounds.width - max(size.width + 34, 62)) / 2,
                         y: titleBaseline(in: bounds, height: 58) - title,
                         width: max(size.width + 34, 62), height: 58)
        NSColor(calibratedWhite: 0.11, alpha: 0.9 * fade).setFill()
        NSBezierPath(roundedRect: box, xRadius: 10, yRadius: 10).fill()
        NSColor(calibratedWhite: 0.5, alpha: 0.85 * fade).setStroke()
        let edge = NSBezierPath(roundedRect: box, xRadius: 10, yRadius: 10)
        edge.lineWidth = 1
        edge.stroke()
        drawn.draw(at: NSPoint(x: box.midX - size.width / 2, y: box.midY - size.height / 2))
    }

    /// One line, measured but not drawn: what a block of two needs to lay itself
    /// out before either of them appears.
    private static func line(_ text: String, size: CGFloat, alpha: Double,
                             in bounds: NSRect) -> (text: NSAttributedString, height: CGFloat) {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center
        paragraph.lineHeightMultiple = 1.08
        let drawn = NSAttributedString(string: text, attributes: [
            .font: NSFont.systemFont(ofSize: min(size, bounds.width / 26), weight: .semibold),
            .foregroundColor: NSColor.white.withAlphaComponent(0.97 * alpha),
            .paragraphStyle: paragraph,
        ])
        let width = bounds.width - 2 * max(bounds.width * 0.06, 28)
        let box = drawn.boundingRect(with: NSSize(width: width, height: .greatestFiniteMagnitude),
                                     options: [.usesLineFragmentOrigin, .usesFontLeading])
        return (drawn, box.height)
    }

    private static func place(_ text: NSAttributedString, in bounds: NSRect, top: CGFloat) {
        let margin = max(bounds.width * 0.06, 28)
        let width = bounds.width - 2 * margin
        let box = text.boundingRect(with: NSSize(width: width, height: .greatestFiniteMagnitude),
                                    options: [.usesLineFragmentOrigin, .usesFontLeading])
        text.draw(with: NSRect(x: margin, y: top - box.height, width: width, height: box.height),
                  options: [.usesLineFragmentOrigin, .usesFontLeading])
    }

    /// Centred in the middle of the frame, wrapped to the frame's own width. A
    /// phone gets the same film in a tall window, and a line set for 1440 points
    /// runs off both edges of 760 -- so the size follows the width and the text
    /// wraps rather than being cropped.
    private static func draw(_ text: String, size: CGFloat, alpha: Double, in bounds: NSRect) {
        let drawn = line(text, size: size, alpha: alpha, in: bounds)
        place(drawn.text, in: bounds,
              top: titleBaseline(in: bounds, height: drawn.height) + drawn.height)
    }
}
