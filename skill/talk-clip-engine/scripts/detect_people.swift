// Read JPG paths from argv, print one JSON line per image with Vision human + face rectangles
// (normalized, origin top-left).
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("{\"path\":\"\(path)\",\"error\":1}"); continue
    }
    let hr = VNDetectHumanRectanglesRequest()
    hr.upperBodyOnly = false
    let fr = VNDetectFaceRectanglesRequest()
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([hr, fr])
    func box(_ o: VNDetectedObjectObservation) -> String {
        let b = o.boundingBox
        return String(format: "[%.4f,%.4f,%.4f,%.4f,%.3f]", b.minX, 1 - b.maxY, b.width, b.height, o.confidence)
    }
    let hs = (hr.results ?? []).map(box).joined(separator: ",")
    let fs = (fr.results ?? []).map(box).joined(separator: ",")
    print("{\"path\":\"\(path)\",\"humans\":[\(hs)],\"faces\":[\(fs)]}")
}
