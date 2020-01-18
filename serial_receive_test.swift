import Foundation

let proc = Process()
proc.executableURL = URL(fileReferenceLiteralResourceName: "/home/pi/dist/serial_forwarding/serial_forwarding")
proc.arguments = []
let pipe = Pipe()
proc.standardOutput = pipe
try? proc.run()

print("Process is running")
