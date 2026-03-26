#!/usr/bin/env swift

import AppKit
import Foundation

struct Config {
    let message: String
    let tabHint: String
    let seconds: Double
    let windowTarget: String
    let paneId: String
    let sessionName: String
    let clientTTY: String
    let paneCount: Int
    let paneTitle: String
}

func usage() -> Never {
    FileHandle.standardError.write(Data("Usage: poc_notify_overlay.swift <message> <tab-hint> <seconds> <window-target> <pane-id> <session-name> <client-tty> <pane-count> <pane-title>\n".utf8))
    exit(1)
}

let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 9 else {
    usage()
}

let message = args[0]
let tabHint = args[1]
let seconds = Double(args[2]) ?? 6.0
let config = Config(
    message: message,
    tabHint: tabHint,
    seconds: max(1.0, seconds),
    windowTarget: args[3],
    paneId: args[4],
    sessionName: args[5],
    clientTTY: args[6],
    paneCount: Int(args[7]) ?? 1,
    paneTitle: args[8]
)

final class OverlayPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

func runAppleScript(_ source: String, args: [String] = []) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
    process.arguments = ["-"] + args
    let stdin = Pipe()
    process.standardInput = stdin
    process.standardOutput = Pipe()
    process.standardError = Pipe()
    do {
        try process.run()
        stdin.fileHandleForWriting.write(Data(source.utf8))
        stdin.fileHandleForWriting.closeFile()
        process.waitUntilExit()
    } catch {
    }
}

func focusTarget(windowTarget: String, sessionName: String, paneId: String, clientTTY: String, tabHint: String, paneCount: Int, paneTitle: String) {
    let escapedWindowTarget = windowTarget.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    let escapedSessionName = sessionName.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    let escapedPaneId = paneId.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    let escapedClientTTY = clientTTY.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    let escapedTabHint = tabHint.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
    let escapedPaneTitle = paneTitle.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")

    let script = """
tell application id \"com.googlecode.iterm2\"
  activate
  tell first window
    set targetIndex to 1
    set desiredTabHint to \"\(escapedTabHint)\"
    set desiredPaneCount to \(paneCount)
    set desiredPaneTitle to \"\(escapedPaneTitle)\"
    set rank to 0
    repeat with tabRef in tabs
      set rank to rank + 1
      set tabSessionCount to count of sessions of tabRef
      try
        set tabTitle to name of current session of tabRef
      on error
        set tabTitle to \"\"
      end try
      if tabSessionCount is desiredPaneCount then
        if desiredPaneCount > 1 then
          set targetIndex to rank
          exit repeat
        else if desiredPaneTitle is not \"\" and tabTitle contains desiredPaneTitle then
          set targetIndex to rank
          exit repeat
        end if
      end if
      if desiredTabHint is not \"\" and tabTitle contains desiredTabHint then
        set targetIndex to rank
        exit repeat
      else if tabTitle contains \"\(escapedSessionName)\" then
        set targetIndex to rank
      end if
    end repeat
    try
      select (tab targetIndex)
    end try
  end tell
end tell
do shell script \"TMUX= tmux select-window -t \\\"\(escapedWindowTarget)\\\" >/dev/null 2>&1; TMUX= tmux select-pane -t \\\"\(escapedPaneId)\\\" >/dev/null 2>&1\"
"""

    _ = escapedClientTTY
    runAppleScript(script)
}

func closeOverlay(after delay: Double, panel: NSPanel) {
    DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
        NSAnimationContext.runAnimationGroup({ context in
            context.duration = 0.2
            panel.animator().alphaValue = 0
        }, completionHandler: {
            NSApp.terminate(nil)
        })
    }
}

final class OverlayView: NSVisualEffectView {
    var onTab: (() -> Void)?
    var onEscape: (() -> Void)?

    override var acceptsFirstResponder: Bool { true }

    override func keyDown(with event: NSEvent) {
        switch event.keyCode {
        case 48:
            onTab?()
        case 53:
            onEscape?()
        default:
            super.keyDown(with: event)
        }
    }

    override func performKeyEquivalent(with event: NSEvent) -> Bool {
        if event.keyCode == 48 {
            onTab?()
            return true
        }
        if event.keyCode == 53 {
            onEscape?()
            return true
        }
        return super.performKeyEquivalent(with: event)
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let screenFrame = NSScreen.main?.visibleFrame ?? NSScreen.screens.first?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
let panelSize = NSSize(width: 560, height: config.tabHint.isEmpty ? 170 : 210)
let panelOrigin = NSPoint(
    x: screenFrame.midX - panelSize.width / 2,
    y: screenFrame.midY - panelSize.height / 2
)

let panel = OverlayPanel(
    contentRect: NSRect(origin: panelOrigin, size: panelSize),
    styleMask: [.borderless],
    backing: .buffered,
    defer: false
)
panel.level = .statusBar
panel.isFloatingPanel = true
panel.hidesOnDeactivate = false
panel.backgroundColor = .clear
panel.isOpaque = false
panel.hasShadow = true
panel.ignoresMouseEvents = false
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .transient, .ignoresCycle]

let contentView = OverlayView(frame: NSRect(origin: .zero, size: panelSize))
contentView.material = .hudWindow
contentView.blendingMode = .behindWindow
contentView.state = .active
contentView.wantsLayer = true
contentView.layer?.cornerRadius = 22
contentView.layer?.masksToBounds = true
contentView.layer?.borderWidth = 1
contentView.layer?.borderColor = NSColor.white.withAlphaComponent(0.12).cgColor
panel.contentView = contentView

func makeLabel(text: String, font: NSFont, color: NSColor, frame: NSRect, alignment: NSTextAlignment = .center) -> NSTextField {
    let label = NSTextField(labelWithString: text)
    label.frame = frame
    label.font = font
    label.textColor = color
    label.alignment = alignment
    label.lineBreakMode = .byWordWrapping
    label.maximumNumberOfLines = 0
    label.backgroundColor = .clear
    return label
}

let titleLabel = makeLabel(
    text: "Hive notify",
    font: .systemFont(ofSize: 17, weight: .semibold),
    color: NSColor.white.withAlphaComponent(0.96),
    frame: NSRect(x: 24, y: panelSize.height - 52, width: panelSize.width - 48, height: 24)
)
contentView.addSubview(titleLabel)

let messageLabel = makeLabel(
    text: config.message,
    font: .systemFont(ofSize: 24, weight: .medium),
    color: NSColor.white,
    frame: NSRect(x: 30, y: config.tabHint.isEmpty ? 42 : 76, width: panelSize.width - 60, height: 64)
)
contentView.addSubview(messageLabel)

if !config.tabHint.isEmpty {
    let hintLabel = makeLabel(
        text: "按 Tab 切到 \(config.tabHint)，按 Esc 关闭",
        font: .systemFont(ofSize: 17, weight: .regular),
        color: NSColor.white.withAlphaComponent(0.86),
        frame: NSRect(x: 30, y: 34, width: panelSize.width - 60, height: 32)
    )
    contentView.addSubview(hintLabel)
}

contentView.onTab = {
    focusTarget(
        windowTarget: config.windowTarget,
        sessionName: config.sessionName,
        paneId: config.paneId,
        clientTTY: config.clientTTY,
        tabHint: config.tabHint,
        paneCount: config.paneCount,
        paneTitle: config.paneTitle
    )
    closeOverlay(after: 0.1, panel: panel)
}

contentView.onEscape = {
    closeOverlay(after: 0.1, panel: panel)
}

panel.alphaValue = 0
panel.orderFrontRegardless()
NSApp.activate(ignoringOtherApps: true)
panel.makeKeyAndOrderFront(nil)
panel.orderFrontRegardless()
panel.makeFirstResponder(contentView)
DispatchQueue.main.async {
    panel.makeKey()
    panel.makeMain()
    panel.makeFirstResponder(contentView)
}

NSAnimationContext.runAnimationGroup { context in
    context.duration = 0.12
    panel.animator().alphaValue = 1
}

closeOverlay(after: config.seconds, panel: panel)

app.run()
