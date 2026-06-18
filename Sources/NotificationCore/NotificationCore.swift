import Foundation

public struct CLIError: Error, CustomStringConvertible, Equatable {
    public let message: String
    public let code: Int32

    public init(_ message: String, code: Int32 = 2) {
        self.message = message
        self.code = code
    }

    public var description: String {
        message
    }
}

public enum Command: Equatable {
    case authStatus
    case requestAccess
    case send(SendOptions)
}

public struct SendOptions: Equatable {
    public var title: String
    public var subtitle: String?
    public var body: String?

    public init(title: String, subtitle: String?, body: String?) {
        self.title = title
        self.subtitle = subtitle
        self.body = body
    }
}

public struct AuthStatusData: Codable, Equatable {
    public var service: String
    public var status: String
    public var authorized: Bool
    public var message: String
    public var nextSteps: [String]

    enum CodingKeys: String, CodingKey {
        case service
        case status
        case authorized
        case message
        case nextSteps = "next_steps"
    }

    public init(service: String, status: String, authorized: Bool, message: String, nextSteps: [String]) {
        self.service = service
        self.status = status
        self.authorized = authorized
        self.message = message
        self.nextSteps = nextSteps
    }
}

public struct RequestAccessData: Codable, Equatable {
    public var service: String
    public var granted: Bool
    public var status: String
    public var message: String
    public var nextSteps: [String]

    enum CodingKeys: String, CodingKey {
        case service
        case granted
        case status
        case message
        case nextSteps = "next_steps"
    }

    public init(service: String, granted: Bool, status: String, message: String, nextSteps: [String]) {
        self.service = service
        self.granted = granted
        self.status = status
        self.message = message
        self.nextSteps = nextSteps
    }
}

public struct SendData: Codable, Equatable {
    public var notificationID: String
    public var delivered: Bool

    enum CodingKeys: String, CodingKey {
        case notificationID = "notification_id"
        case delivered
    }

    public init(notificationID: String, delivered: Bool) {
        self.notificationID = notificationID
        self.delivered = delivered
    }
}

public final class CommandParser {
    private let arguments: [String]

    public init(arguments: [String]) {
        self.arguments = arguments
    }

    public func parse() throws -> Command {
        guard let command = arguments.first else {
            throw CLIError("必须提供命令：auth-status、request-access 或 send。")
        }

        var reader = ArgumentReader(Array(arguments.dropFirst()))
        switch command {
        case "auth-status":
            try reader.ensureNoUnusedArguments()
            return .authStatus
        case "request-access":
            try reader.ensureNoUnusedArguments()
            return .requestAccess
        case "send":
            let options = SendOptions(
                title: try reader.requiredValue(for: "--title"),
                subtitle: try reader.optionalValue(for: "--subtitle"),
                body: try reader.optionalValue(for: "--body")
            )
            try reader.ensureNoUnusedArguments()
            return .send(options)
        case "-h", "--help", "help":
            throw CLIError(helpText(), code: 0)
        default:
            throw CLIError("未知命令：\(command)。")
        }
    }
}

public func notificationAuthData(status: NotificationAuthStatus) -> AuthStatusData {
    let authorized = status.isAuthorized
    let steps = [
        "到「系统设置 > 通知」允许当前运行的 Codex、CodePilot、终端或 notifications-cli 发送通知。",
        "授权后重新运行原通知命令。",
    ]

    let message: String
    switch status {
    case .notDetermined:
        message = "通知权限尚未请求。请运行 request-access 触发系统授权窗口。"
    case .denied:
        message = "没有权限发送通知。请到「系统设置 > 通知」允许当前运行的 Codex、CodePilot、终端或 notifications-cli 发送通知。"
    case .authorized:
        message = "当前进程已获得通知权限。"
    case .provisional:
        message = "当前进程已获得临时通知权限。"
    case .ephemeral:
        message = "当前进程已获得临时会话通知权限。"
    case .unknown:
        message = "当前通知权限状态未知，请到系统设置检查通知权限。"
    }

    return AuthStatusData(
        service: "notifications",
        status: status.rawValue,
        authorized: authorized,
        message: message,
        nextSteps: authorized ? [] : steps
    )
}

public enum NotificationAuthStatus: String, Equatable {
    case notDetermined = "not_determined"
    case denied
    case authorized
    case provisional
    case ephemeral
    case unknown

    public var isAuthorized: Bool {
        switch self {
        case .authorized, .provisional, .ephemeral:
            return true
        case .notDetermined, .denied, .unknown:
            return false
        }
    }
}

public func encodeSuccess<Data: Codable>(_ data: Data) -> String {
    #"{"success":true,"data":\#(encode(data)),"message":"ok"}"#
}

public func encodeFailure(message: String) -> String {
    #"{"success":false,"data":{},"message":\#(encode(message))}"#
}

public func helpText() -> String {
    """
    用法：
      notifications-cli auth-status
      notifications-cli request-access
      notifications-cli send --title 标题 [--subtitle 副标题] [--body 内容]
    """
}

private func encode<Value: Codable>(_ value: Value) -> String {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.withoutEscapingSlashes]
    let data = try! encoder.encode(value)
    return String(data: data, encoding: .utf8)!
}

private struct ArgumentReader {
    private var arguments: [String]

    init(_ arguments: [String]) {
        self.arguments = arguments
    }

    mutating func requiredValue(for name: String) throws -> String {
        guard let value = try optionalValue(for: name) else {
            throw CLIError("缺少必填参数 \(name)。")
        }
        return value
    }

    mutating func optionalValue(for name: String) throws -> String? {
        guard let index = arguments.firstIndex(of: name) else {
            return nil
        }
        let valueIndex = arguments.index(after: index)
        guard valueIndex < arguments.endIndex else {
            throw CLIError("参数 \(name) 缺少值。")
        }
        let value = arguments[valueIndex]
        arguments.remove(at: valueIndex)
        arguments.remove(at: index)
        return value
    }

    func ensureNoUnusedArguments() throws {
        guard arguments.isEmpty else {
            throw CLIError("无法识别参数：\(arguments.joined(separator: " "))。")
        }
    }
}
