import Cocoa
import UniformTypeIdentifiers

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    let log = NSTextView()
    let status = NSTextField(labelWithString: "Ready — start with Check Mac")
    let spinner = NSProgressIndicator()
    var buttons: [NSButton] = []
    var process: Process?
    var sessionLog: FileHandle?
    var lastDiagnostic: String?
    var input: FileHandle?
    let transferProgress = NSProgressIndicator()
    var cancelButton: NSButton!
    var activity: NSObjectProtocol?
    var latestBackup: URL? {
        get { UserDefaults.standard.string(forKey: "latestBackup").map { URL(fileURLWithPath: $0) } }
        set { UserDefaults.standard.set(newValue?.path, forKey: "latestBackup") }
    }
    var latestRun: URL? {
        get { UserDefaults.standard.string(forKey: "latestRun").map { URL(fileURLWithPath: $0) } }
        set { UserDefaults.standard.set(newValue?.path, forKey: "latestRun") }
    }
    var resources: URL { Bundle.main.resourceURL! }
    func applicationDidFinishLaunching(_ notification: Notification) {
        let logs = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/Tonal Freedom")
        try? FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
        let logURL = logs.appendingPathComponent("session-" + UUID().uuidString + ".log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        sessionLog = try? FileHandle(forWritingTo: logURL)
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 840),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "Tonal Freedom"
        window.minSize = NSSize(width: 840, height: 760)
        window.delegate = self
        let stack = NSStackView()
        stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor, constant: -24)])
        let title = NSTextField(labelWithString: "Tonal Freedom")
        title.font = .systemFont(ofSize: 28, weight: .bold); stack.addArrangedSubview(title)
        let subtitle = NSTextField(wrappingLabelWithString: "Tonal 1 • Standalone Mac app\nFollow the steps in order. Backup, patching and verified boot flashing run here.")
        subtitle.textColor = .secondaryLabelColor; stack.addArrangedSubview(subtitle)
        addRow(stack, "1  Check Mac", #selector(check), "Verify the prepared tools, bundled APKs, USB library and ADB key.")
        addRow(stack, "2  Back up Tonal…", #selector(backup), "Choose a backup folder. Connect USB and power cycle when prompted.")
        addRow(stack, "3  Patch backed-up boot", #selector(patch), "Use the verified backup automatically; keep the original unchanged.")
        addRow(stack, "4  Flash boot…", #selector(flash), "Check the device and backup, confirm boot-only flashing, then verify read-back.")
        addRow(stack, "5  Set up Wi-Fi ADB", #selector(connect), "One-time USB setup: save and verify the Tonal’s authenticated Wi-Fi connection.")
        addRow(stack, "6  Install Magisk…", #selector(install), "Install bundled Magisk over Wi-Fi. Use Install APK below for other apps.")
        addRow(stack, "7  Install launcher", #selector(installLauncher), "Install and open Text Launcher over Wi-Fi so you can choose other apps.")
        addRow(stack, "8  Disable OTA updates", #selector(blockOTA), "Block system and Tonal app updates across reboots. Motor firmware stays unchanged.")
        let utility = NSStackView(); utility.spacing = 10
        for (name, action) in [("Show output", #selector(showOutput)), ("Show backup", #selector(showBackup)), ("Prepare ADB key", #selector(prepare)), ("Guide", #selector(guide))] {
            let button = NSButton(title: name, target: self, action: action)
            utility.addArrangedSubview(button); buttons.append(button)
        }
        stack.addArrangedSubview(utility)
        let wirelessActions = NSStackView(); wirelessActions.spacing = 10
        for (name, action) in [("Reconnect Wi-Fi…", #selector(reconnectWireless)), ("Install APK…", #selector(installAPK)), ("Allow OTA updates…", #selector(allowOTA))] {
            let button = NSButton(title: name, target: self, action: action)
            wirelessActions.addArrangedSubview(button); buttons.append(button)
        }
        stack.addArrangedSubview(wirelessActions)
        let progress = NSStackView(); progress.spacing = 10
        spinner.style = .spinning; spinner.controlSize = .small
        progress.addArrangedSubview(spinner); progress.addArrangedSubview(status)
        stack.addArrangedSubview(progress)
        status.lineBreakMode = .byWordWrapping
        status.maximumNumberOfLines = 2
        transferProgress.style = .bar; transferProgress.isIndeterminate = false
        transferProgress.minValue = 0; transferProgress.maxValue = 100
        stack.addArrangedSubview(transferProgress)
        transferProgress.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        cancelButton = NSButton(title: "Cancel current step", target: self, action: #selector(cancel))
        cancelButton.isEnabled = false; stack.addArrangedSubview(cancelButton)
        let scroll = NSScrollView(); scroll.hasVerticalScroller = true; scroll.borderType = .bezelBorder
        log.isEditable = false; log.isSelectable = true; log.font = .monospacedSystemFont(ofSize: 14, weight: .regular)
        log.textColor = .textColor
        log.backgroundColor = .textBackgroundColor
        log.drawsBackground = true
        log.textContainerInset = NSSize(width: 12, height: 12)
        log.autoresizingMask = [.width]; log.isVerticallyResizable = true
        log.textContainer?.widthTracksTextView = true; scroll.documentView = log
        stack.addArrangedSubview(scroll)
        scroll.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 170).isActive = true
        append("Your original image is never modified. Each patch gets its own output folder.\nA successful Mac check does not establish Tonal boot or recovery compatibility.\n")
        let menu = NSMenu(); let appMenu = NSMenu(); let appItem = NSMenuItem(); appItem.submenu = appMenu
        appMenu.addItem(withTitle: "Quit Tonal Freedom", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        menu.addItem(appItem)
        let editItem = NSMenuItem(); let edit = NSMenu(title: "Edit"); editItem.submenu = edit
        edit.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        menu.addItem(editItem); NSApp.mainMenu = menu
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
    }
    func addRow(_ stack: NSStackView, _ title: String, _ action: Selector, _ explanation: String) {
        let row = NSStackView(); row.spacing = 14; row.alignment = .centerY
        let button = NSButton(title: title, target: self, action: action)
        button.widthAnchor.constraint(equalToConstant: 205).isActive = true
        buttons.append(button); row.addArrangedSubview(button)
        let label = NSTextField(wrappingLabelWithString: explanation)
        label.font = .systemFont(ofSize: 12); row.addArrangedSubview(label)
        stack.addArrangedSubview(row); row.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
    }
    func append(_ rawText: String) {
        let text = rawText.replacingOccurrences(of: "\u{001B}\\[[0-9;]*m", with: "", options: .regularExpression)
        sessionLog?.write(Data(text.utf8))
        log.textStorage?.append(NSAttributedString(string: text, attributes: [.font: NSFont.monospacedSystemFont(ofSize: 14, weight: .regular), .foregroundColor: NSColor.textColor]))
        if let storage = log.textStorage, storage.length > 300_000 {
            storage.deleteCharacters(in: NSRange(location: 0, length: storage.length - 250_000))
        }
        log.scrollToEndOfDocument(nil)
    }
    func notice(_ message: String) {
        let alert = NSAlert(); alert.messageText = message; alert.runModal()
    }
    func confirm(_ title: String, _ detail: String, _ action: String) -> Bool {
        let alert = NSAlert(); alert.messageText = title; alert.informativeText = detail
        alert.addButton(withTitle: action); alert.addButton(withTitle: "Cancel")
        return alert.runModal() == .alertFirstButtonReturn
    }
    func run(_ args: [String], _ label: String, completion: ((Bool, String) -> Void)? = nil) {
        guard process == nil else { return }
        let p = Process(); p.executableURL = URL(fileURLWithPath: "/bin/bash")
        p.arguments = [resources.appendingPathComponent("task.sh").path] + args
        var env = ProcessInfo.processInfo.environment; env["PYTHONUNBUFFERED"] = "1"; p.environment = env
        let pipe = Pipe(); p.standardOutput = pipe; p.standardError = pipe
        let stdinPipe = Pipe(); p.standardInput = stdinPipe
        input = stdinPipe.fileHandleForWriting
        cancelButton.isEnabled = !(args.prefix(2).elementsEqual(["device", "flash"]))
        transferProgress.doubleValue = 0
        lastDiagnostic = nil
        process = p; buttons.forEach { $0.isEnabled = false }; spinner.startAnimation(nil)
        status.stringValue = label; append("\n▶ \(label)\n")
        do { try p.run() } catch {
            process = nil; cancelButton.isEnabled = false; input = nil; buttons.forEach { $0.isEnabled = true }; spinner.stopAnimation(nil)
            status.stringValue = "Could not start"; append("\(error)\n"); completion?(false, ""); return
        }
        activity = ProcessInfo.processInfo.beginActivity(options: [.idleSystemSleepDisabled, .userInitiated], reason: label)
        // Read off the main thread so long-running commands keep the interface responsive.
        DispatchQueue.global(qos: .userInitiated).async {
            var output = Data()
            var pending = Data()
            while true {
                let data = pipe.fileHandleForReading.availableData
                if data.isEmpty { break }
                output.append(data)
                if output.count > 1_000_000 { output.removeFirst(output.count - 1_000_000) }
                pending.append(data)
                while let newline = pending.firstIndex(of: 10) {
                    let line = String(decoding: pending.prefix(through: newline), as: UTF8.self)
                    pending.removeSubrange(...newline)
                    DispatchQueue.main.async { self.consume(line) }
                }
            }
            if !pending.isEmpty {
                let text = String(decoding: pending, as: UTF8.self)
                DispatchQueue.main.async { self.append(text) }
            }
            p.waitUntilExit(); let ok = p.terminationStatus == 0
            let result = String(decoding: output, as: UTF8.self)
            DispatchQueue.main.async {
                if let activity = self.activity { ProcessInfo.processInfo.endActivity(activity); self.activity = nil }
                self.process = nil; self.cancelButton.isEnabled = false; self.input = nil; self.buttons.forEach { $0.isEnabled = true }; self.spinner.stopAnimation(nil)
                self.status.stringValue = ok ? "Finished — \(label)" : (p.terminationStatus == 15 ? "Cancelled" : self.lastDiagnostic ?? "Failed — see log above")
                self.append(ok ? "✓ Command completed.\n" : "✗ Exit code \(p.terminationStatus).\n")
                completion?(ok, result)
            }
        }
    }
    @objc func check() { run(["check"], "Checking this Mac") }
    @objc func prepare() { run(["prepare"], "Preparing the dedicated ADB key") }
    func consume(_ line: String) {
        guard let marker = line.range(of: "TONAL_EVENT "),
              let data = String(line[marker.upperBound...]).data(using: .utf8),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { append(line); return }
        let message = value["message"] as? String ?? ""
        if value["kind"] as? String == "status" { lastDiagnostic = message }
        if value["kind"] as? String == "confirm" {
            let yes = confirm("Ready to flash boot", message + "\n\nKeep USB connected and power on until verification finishes.", "Flash boot")
            input?.write(Data((yes ? "FLASH\n" : "CANCEL\n").utf8))
        } else {
            status.stringValue = message
            if let percent = value["percent"] as? Double {
                transferProgress.doubleValue = percent
                status.stringValue = String(format: "%.1f%% — %@", percent, message)
            } else { append(message + "\n") }
        }
    }
    @objc func cancel() { process?.terminate(); status.stringValue = "Cancelling — incomplete work will not be marked successful" }
    @objc func showBackup() {
        if let folder = latestBackup { NSWorkspace.shared.open(folder) }
        else { notice("Complete step 2 first.") }
    }
    @objc func backup() {
        if let saved = UserDefaults.standard.string(forKey: "pendingBackup"),
           FileManager.default.fileExists(atPath: saved + "/resume.json"),
           !FileManager.default.fileExists(atPath: saved + "/backup.json") {
            let alert = NSAlert(); alert.messageText = "Resume the incomplete full backup?"
            alert.informativeText = "Saved chunks will be verified against this Tonal before continuing.\n" + saved
            alert.addButton(withTitle: "Resume"); alert.addButton(withTitle: "New backup"); alert.addButton(withTitle: "Cancel")
            let choice = alert.runModal()
            if choice == .alertFirstButtonReturn { startBackup(URL(fileURLWithPath: saved)); return }
            if choice != .alertSecondButtonReturn { return }
        }
        let picker = NSOpenPanel(); picker.canChooseDirectories = true; picker.canChooseFiles = false
        picker.canCreateDirectories = true; picker.title = "Choose a backup destination or an incomplete backup to resume"
        guard picker.runModal() == .OK, let parent = picker.url else { return }
        if FileManager.default.fileExists(atPath: parent.appendingPathComponent("resume.json").path) {
            startBackup(parent); return
        }
        let folder = parent.appendingPathComponent("Tonal Backup " + UUID().uuidString)
        do { try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true) }
        catch { notice(error.localizedDescription); return }
        startBackup(folder)
    }
    func startBackup(_ folder: URL) {
        UserDefaults.standard.set(folder.path, forKey: "pendingBackup")
        run(["device", "backup", folder.path], "Connect USB and power cycle Tonal to begin backup") { ok, _ in
            if ok {
                UserDefaults.standard.removeObject(forKey: "pendingBackup")
                self.latestBackup = folder
                self.status.stringValue = "Backup verified — ready to patch. Keep a second copy separately."
                self.transferProgress.doubleValue = 100
            }
        }
    }
    @objc func patch() {
        guard let backup = latestBackup else { notice("Complete the app’s full backup in step 2 first."); return }
        let original = backup.appendingPathComponent("boot.bin")
        do {
            let base = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            let folder = base.appendingPathComponent("Tonal Freedom/Runs/\(UUID().uuidString)")
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            try FileManager.default.copyItem(at: original, to: folder.appendingPathComponent("boot.bin"))
            for name in ["Magisk-v27.0.apk", "textlauncher.apk"] {
                try FileManager.default.copyItem(at: resources.appendingPathComponent(name), to: folder.appendingPathComponent(name))
            }
            run(["patch", folder.path], "Patching the backed-up boot image") { ok, _ in
                guard ok else { return }
                self.run(["device", "seal", folder.path, backup.path], "Verifying backup and linking the patched image") { verified, _ in
                    if verified {
                        self.latestRun = folder
                        self.append("OUTPUT: \(folder.path)/boot.patched.img\n")
                        self.status.stringValue = "Patch and backup verified — ready for step 4"
                        self.transferProgress.doubleValue = 100
                    }
                }
            }
        } catch { notice("Could not prepare image: \(error.localizedDescription)") }
    }
    @objc func showOutput() {
        guard let folder = latestRun else { notice("Patch an image first to create an output folder."); return }
        NSWorkspace.shared.open(folder)
    }
    @objc func flash() {
        guard let folder = latestRun,
              FileManager.default.fileExists(atPath: folder.appendingPathComponent("patch.json").path) else {
            notice("Complete the app’s backup and patch steps first."); return
        }
        run(["device", "flash", folder.path], "Validating backup, then waiting for Tonal — power cycle when prompted") { ok, _ in
            if ok {
                self.status.stringValue = "Boot write and read-back verified — power cycle, then complete Wi-Fi ADB setup while USB remains connected"
                self.transferProgress.doubleValue = 100
            }
        }
    }
    @objc func connect() {
        run(["wireless", "devices"], "Finding the USB-connected Tonal for one-time Wi-Fi setup") { ok, result in
            guard ok else { return }
            let devices = self.serials(result).filter { !$0.contains(":") && !$0.hasPrefix("emulator-") }
            guard !devices.isEmpty else {
                self.notice("Keep USB connected for initial setup. Boot the newly patched Tonal and connect it to Wi-Fi in Android Settings, then retry."); return
            }
            let alert = NSAlert(); alert.messageText = "Set up wireless access"
            alert.informativeText = "Choose the USB-connected Tonal. Complete any Magisk additional setup on its screen, then grant Shell superuser access when prompted. The app will configure persistent authenticated Wi-Fi ADB and verify the connection."
            let picker = NSPopUpButton(frame: NSRect(x: 0, y: 0, width: 340, height: 28))
            picker.addItems(withTitles: devices); alert.accessoryView = picker
            alert.addButton(withTitle: "Set up Wi-Fi"); alert.addButton(withTitle: "Cancel")
            guard alert.runModal() == .alertFirstButtonReturn, let serial = picker.titleOfSelectedItem else { return }
            self.run(["wireless", "setup", serial], "Setting up persistent Wi-Fi ADB") { ready, _ in
                if ready { self.status.stringValue = "Wi-Fi saved — unplug USB and test Reconnect Wi-Fi, including after a power cycle" }
            }
        }
    }
    @objc func reconnectWireless() {
        let alert = NSAlert(); alert.messageText = "Reconnect to your Tonal"
        alert.informativeText = "Leave blank to use the saved address. If your router changed it, enter the Tonal’s new Wi-Fi IP from Android Settings or your router."
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 340, height: 28))
        field.placeholderString = "Saved address, or e.g. 192.168.1.50"
        alert.accessoryView = field
        alert.addButton(withTitle: "Connect"); alert.addButton(withTitle: "Cancel")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        run(["wireless", "connect", field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)], "Reconnecting to the saved Tonal over Wi-Fi")
    }
    @objc func installAPK() {
        let picker = NSOpenPanel(); picker.canChooseDirectories = false; picker.allowsMultipleSelection = false
        picker.title = "Choose an APK to install on your Tonal over Wi-Fi"
        guard picker.runModal() == .OK, let apk = picker.url else { return }
        guard apk.pathExtension.lowercased() == "apk" else { notice("Choose an APK file."); return }
        run(["wireless", "install", apk.path], "Connecting to Tonal and installing \(apk.lastPathComponent)")
    }
    func serials(_ output: String) -> [String] {
        output.components(separatedBy: .newlines).compactMap { line in
            let parts = line.split(whereSeparator: { $0.isWhitespace })
            return parts.count >= 2 && parts[1] == "device" ? String(parts[0]) : nil
        }
    }
    @objc func install() {
        run(["wireless", "install", resources.appendingPathComponent("Magisk-v27.0.apk").path], "Connecting to Tonal and installing Magisk over Wi-Fi")
    }
    @objc func installLauncher() {
        run(["wireless", "launcher"], "Installing and opening Text Launcher on the Tonal")
    }
    @objc func blockOTA() {
        run(["wireless", "block-ota"], "Disabling and verifying system and Tonal app OTA updates")
    }
    @objc func allowOTA() {
        let alert = NSAlert(); alert.messageText = "Allow Tonal updates again?"
        alert.informativeText = "Remove the startup block and enable the system and Tonal app updaters. Future updates may replace the modified software."
        alert.addButton(withTitle: "Allow updates"); alert.addButton(withTitle: "Cancel")
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        run(["wireless", "allow-ota"], "Restoring and verifying Tonal OTA updates")
    }
    @objc func guide() { NSWorkspace.shared.open(resources.appendingPathComponent("MACOS.md")) }
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if process != nil { notice("A tool is still running. Wait for the operation to finish, or cancel if that step allows it."); return false }
        return true
    }
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if process != nil { notice("Wait for the operation to finish before quitting. Never interrupt a boot write."); return .terminateCancel }
        return .terminateNow
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
