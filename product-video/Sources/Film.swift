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

    /// Titles are centred, and the keys pressed after one appear in the same
    /// place, so a viewer's eye never leaves the middle of the frame.
    static func titleBaseline(in bounds: NSRect, height: CGFloat) -> CGFloat {
        (bounds.height - height) / 2
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
        NSColor.black.withAlphaComponent(0.5 * alpha).setFill()
        bounds.fill()
        draw(text, size: 52 * scale, alpha: alpha, in: bounds)
    }

    static func drawCard(_ text: String, then second: (text: String, at: Double)?,
                         start: Double, end: Double, now at: Double,
                         handingOver: Bool = false, in bounds: NSRect) {
        let (alpha, scale) = pop(start, end, now: at, handingOver: handingOver)
        guard alpha > 0.01 else { return }
        NSColor.black.withAlphaComponent(0.85 * alpha).setFill()
        bounds.fill()

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
