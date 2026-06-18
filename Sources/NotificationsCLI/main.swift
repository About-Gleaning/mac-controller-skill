import Foundation
import NotificationCore
import UserNotifications

private let launchOptions = LaunchOptions(arguments: Array(CommandLine.arguments.dropFirst()))
private let parser = CommandParser(arguments: launchOptions.commandArguments)

do {
    let command = try parser.parse()
    let controller = NotificationsController()
    let output = try controller.run(command)
    write(output: output, to: launchOptions.outputPath)
    print(output)
} catch let error as CLIError {
    if error.code == 0 {
        write(output: error.message, to: launchOptions.outputPath)
        print(error.message)
    } else {
        let output = encodeFailure(message: error.message)
        write(output: output, to: launchOptions.outputPath)
        print(output)
    }
    exit(error.code)
} catch {
    let output = encodeFailure(message: normalizeError(error))
    write(output: output, to: launchOptions.outputPath)
    print(output)
    exit(1)
}

private struct LaunchOptions {
    var commandArguments: [String]
    var outputPath: String? = nil

    init(arguments: [String]) {
        var remaining = arguments
        if let index = remaining.firstIndex(of: "--output-json") {
            let valueIndex = remaining.index(after: index)
            if valueIndex < remaining.endIndex {
                outputPath = remaining[valueIndex]
                remaining.remove(at: valueIndex)
                remaining.remove(at: index)
            }
        }
        commandArguments = remaining
    }
}

private final class NotificationsController {
    private lazy var center = UNUserNotificationCenter.current()

    func run(_ command: Command) throws -> String {
        try ensureAppBundleContext()
        switch command {
        case .authStatus:
            return encodeSuccess(try authStatusData())
        case .requestAccess:
            return encodeSuccess(try requestAccessData())
        case .send(let options):
            try ensureNotificationAccess()
            return encodeSuccess(try send(options))
        }
    }

    private func ensureAppBundleContext() throws {
        // UserNotifications 依赖 LaunchServices 识别当前 bundle；裸 CLI 会触发系统级异常。
        guard Bundle.main.bundlePath.hasSuffix(".app") else {
            throw CLIError("通知命令必须通过 scripts/notifications.py 启动，以便在临时 app bundle 中运行。", code: 1)
        }
    }

    private func authStatusData() throws -> AuthStatusData {
        notificationAuthData(status: try currentStatus())
    }

    private func requestAccessData() throws -> RequestAccessData {
        let granted = try requestAccess()
        let statusData = try authStatusData()
        return RequestAccessData(
            service: statusData.service,
            granted: granted,
            status: statusData.status,
            message: statusData.message,
            nextSteps: statusData.nextSteps
        )
    }

    private func send(_ options: SendOptions) throws -> SendData {
        let content = UNMutableNotificationContent()
        content.title = options.title
        if let subtitle = options.subtitle {
            content.subtitle = subtitle
        }
        if let body = options.body {
            content.body = body
        }
        content.sound = .default

        let id = UUID().uuidString
        let request = UNNotificationRequest(identifier: id, content: content, trigger: nil)

        let semaphore = DispatchSemaphore(value: 0)
        var addError: Error?
        center.add(request) { error in
            addError = error
            semaphore.signal()
        }
        semaphore.wait()

        if let addError {
            throw addError
        }
        return SendData(notificationID: id, delivered: true)
    }

    private func ensureNotificationAccess() throws {
        let status = try currentStatus()
        if status.isAuthorized {
            return
        }
        if status == .denied {
            throw CLIError(notificationAuthData(status: status).message, code: 1)
        }
        if try requestAccess() {
            return
        }
        throw CLIError(notificationAuthData(status: try currentStatus()).message, code: 1)
    }

    @discardableResult
    private func requestAccess() throws -> Bool {
        let status = try currentStatus()
        if status.isAuthorized {
            return true
        }
        if status == .denied {
            throw CLIError(notificationAuthData(status: status).message, code: 1)
        }

        let semaphore = DispatchSemaphore(value: 0)
        var granted = false
        var requestError: Error?
        center.requestAuthorization(options: [.alert, .sound]) { ok, error in
            granted = ok
            requestError = error
            semaphore.signal()
        }
        semaphore.wait()

        if let requestError {
            throw requestError
        }
        return granted
    }

    private func currentStatus() throws -> NotificationAuthStatus {
        let semaphore = DispatchSemaphore(value: 0)
        var settings: UNNotificationSettings?
        center.getNotificationSettings { value in
            settings = value
            semaphore.signal()
        }
        semaphore.wait()

        guard let settings else {
            throw CLIError("无法读取通知权限状态。", code: 1)
        }
        return mapStatus(settings.authorizationStatus)
    }

    private func mapStatus(_ status: UNAuthorizationStatus) -> NotificationAuthStatus {
        switch status {
        case .notDetermined:
            return .notDetermined
        case .denied:
            return .denied
        case .authorized:
            return .authorized
        case .provisional:
            return .provisional
        case .ephemeral:
            return .ephemeral
        @unknown default:
            return .unknown
        }
    }
}

private func normalizeError(_ error: Error) -> String {
    if let cliError = error as? CLIError {
        return cliError.message
    }
    let nsError = error as NSError
    if nsError.domain == "UNErrorDomain", nsError.code == 1 {
        return "通知发送失败。请先运行 request-access，并到「系统设置 > 通知」允许 notifications-cli 发送通知。"
    }
    let text = error.localizedDescription
    return text.isEmpty ? "通知操作失败。" : text
}

private func write(output: String, to path: String?) {
    guard let path else {
        return
    }
    try? output.write(toFile: path, atomically: true, encoding: .utf8)
}
