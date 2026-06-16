import Foundation

public let dateFormatHint = "YYYY-MM-DD HH:MM:SS"
public let defaultListLimit = 20
public let maxUnscopedListLimit = 20
public let maxScopedListLimit = 50
public let maxListOffset = 500

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
    case create(CreateOptions)
    case list(ListOptions)
    case update(UpdateOptions)
    case complete(CompleteOptions)
}

public struct CreateOptions: Equatable {
    public var name: String
    public var list: String?
    public var body: String?
    public var due: Date?
    public var priority: Int?
}

public struct ListOptions: Equatable {
    public var list: String?
    public var query: String?
    public var completed: Bool?
    public var limit: Int
    public var offset: Int
}

public struct UpdateOptions: Equatable {
    public var id: String
    public var name: String?
    public var body: String?
    public var due: Date?
    public var clearDue: Bool
    public var priority: Int?
    public var completed: Bool?
}

public struct CompleteOptions: Equatable {
    public var id: String
}

public struct ReminderOutput: Codable, Equatable {
    public var id: String
    public var name: String
    public var list: String
    public var body: String?
    public var completed: Bool
    public var dueDate: String?
    public var priority: Int

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case list
        case body
        case completed
        case dueDate = "due_date"
        case priority
    }

    public init(id: String, name: String, list: String, body: String?, completed: Bool, dueDate: String?, priority: Int) {
        self.id = id
        self.name = name
        self.list = list
        self.body = body
        self.completed = completed
        self.dueDate = dueDate
        self.priority = priority
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(name, forKey: .name)
        try container.encode(list, forKey: .list)
        if let body {
            try container.encode(body, forKey: .body)
        } else {
            try container.encodeNil(forKey: .body)
        }
        try container.encode(completed, forKey: .completed)
        if let dueDate {
            try container.encode(dueDate, forKey: .dueDate)
        } else {
            try container.encodeNil(forKey: .dueDate)
        }
        try container.encode(priority, forKey: .priority)
    }
}

public struct CreateData: Codable, Equatable {
    public var reminder: ReminderOutput

    public init(reminder: ReminderOutput) {
        self.reminder = reminder
    }
}

public struct ListData: Codable, Equatable {
    public var reminders: [ReminderOutput]
    public var count: Int
    public var offset: Int
    public var limit: Int
    public var hasMore: Bool
    public var nextOffset: Int?

    enum CodingKeys: String, CodingKey {
        case reminders
        case count
        case offset
        case limit
        case hasMore = "has_more"
        case nextOffset = "next_offset"
    }

    public init(reminders: [ReminderOutput], count: Int, offset: Int, limit: Int, hasMore: Bool, nextOffset: Int?) {
        self.reminders = reminders
        self.count = count
        self.offset = offset
        self.limit = limit
        self.hasMore = hasMore
        self.nextOffset = nextOffset
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(reminders, forKey: .reminders)
        try container.encode(count, forKey: .count)
        try container.encode(offset, forKey: .offset)
        try container.encode(limit, forKey: .limit)
        try container.encode(hasMore, forKey: .hasMore)
        if let nextOffset {
            try container.encode(nextOffset, forKey: .nextOffset)
        } else {
            try container.encodeNil(forKey: .nextOffset)
        }
    }
}

public struct UpdateData: Codable, Equatable {
    public var id: String
    public var updated: Bool

    public init(id: String, updated: Bool) {
        self.id = id
        self.updated = updated
    }
}

public struct CompleteData: Codable, Equatable {
    public var id: String
    public var completed: Bool

    public init(id: String, completed: Bool) {
        self.id = id
        self.completed = completed
    }
}

public struct EmptyData: Codable, Equatable {}

public final class CommandParser {
    private let arguments: [String]

    public init(arguments: [String]) {
        self.arguments = arguments
    }

    public func parse() throws -> Command {
        guard let command = arguments.first else {
            throw CLIError("必须提供命令：create、list、update 或 complete。")
        }

        var reader = ArgumentReader(Array(arguments.dropFirst()))
        switch command {
        case "create":
            let name = try reader.requiredValue(for: "--name")
            let options = CreateOptions(
                name: name,
                list: try reader.optionalValue(for: "--list"),
                body: try reader.optionalValue(for: "--body"),
                due: try parseDate(try reader.optionalValue(for: "--due")),
                priority: try parsePriority(try reader.optionalValue(for: "--priority"))
            )
            try reader.ensureNoUnusedArguments()
            return .create(options)
        case "list":
            let options = ListOptions(
                list: try reader.optionalValue(for: "--list"),
                query: try reader.optionalValue(for: "--query"),
                completed: try parseBool(try reader.optionalValue(for: "--completed")),
                limit: try parseInt(try reader.optionalValue(for: "--limit")) ?? defaultListLimit,
                offset: try parseInt(try reader.optionalValue(for: "--offset")) ?? 0
            )
            try validateListOptions(options)
            try reader.ensureNoUnusedArguments()
            return .list(options)
        case "update":
            let id = try reader.requiredValue(for: "--id")
            let due = try parseDate(try reader.optionalValue(for: "--due"))
            let clearDue = reader.consumeFlag("--clear-due")
            if clearDue && due != nil {
                throw CLIError("--clear-due 不能和 --due 同时使用。")
            }
            let options = UpdateOptions(
                id: id,
                name: try reader.optionalValue(for: "--name"),
                body: try reader.optionalValue(for: "--body"),
                due: due,
                clearDue: clearDue,
                priority: try parsePriority(try reader.optionalValue(for: "--priority")),
                completed: try parseBool(try reader.optionalValue(for: "--completed"))
            )
            try reader.ensureNoUnusedArguments()
            return .update(options)
        case "complete":
            let options = CompleteOptions(id: try reader.requiredValue(for: "--id"))
            try reader.ensureNoUnusedArguments()
            return .complete(options)
        case "-h", "--help", "help":
            throw CLIError(helpText(), code: 0)
        default:
            throw CLIError("未知命令：\(command)。")
        }
    }
}

public func parseBool(_ value: String?) throws -> Bool? {
    guard let value else {
        return nil
    }
    switch value.lowercased() {
    case "true":
        return true
    case "false":
        return false
    default:
        throw CLIError("布尔值必须是 true 或 false。")
    }
}

public func parseDate(_ value: String?) throws -> Date? {
    guard let value else {
        return nil
    }
    guard value.count == 19 else {
        throw CLIError("时间格式必须是 \(dateFormatHint)。")
    }
    guard dateFormatter.date(from: value) != nil else {
        throw CLIError("时间格式必须是 \(dateFormatHint)。")
    }
    return dateFormatter.date(from: value)
}

public func formatDate(_ date: Date?) -> String? {
    guard let date else {
        return nil
    }
    return dateFormatter.string(from: date)
}

public func parsePriority(_ value: String?) throws -> Int? {
    guard let priority = try parseInt(value) else {
        return nil
    }
    guard priority >= 0 && priority <= 9 else {
        throw CLIError("优先级必须在 0 到 9 之间。")
    }
    return priority
}

public func validateListOptions(_ options: ListOptions) throws {
    guard options.limit > 0 else {
        throw CLIError("--limit 必须大于 0。")
    }
    guard options.offset >= 0 && options.offset <= maxListOffset else {
        throw CLIError("--offset 必须在 0 到 \(maxListOffset) 之间。")
    }
    let maxLimit = options.query == nil && options.list == nil ? maxUnscopedListLimit : maxScopedListLimit
    guard options.limit <= maxLimit else {
        throw CLIError("当前查询的 --limit 不能超过 \(maxLimit)。请使用 --query、--list 或 --offset 缩小范围。")
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
      reminders-cli create --name 标题 [--list 列表] [--body 备注] [--due "\(dateFormatHint)"] [--priority 0..9]
      reminders-cli list [--list 列表] [--query 关键词] [--completed true|false] [--limit 数量] [--offset 数量]
      reminders-cli update --id ID [--name 标题] [--body 备注] [--due "\(dateFormatHint)"] [--clear-due] [--priority 0..9] [--completed true|false]
      reminders-cli complete --id ID
    """
}

private let dateFormatter: DateFormatter = {
    let formatter = DateFormatter()
    formatter.calendar = Calendar(identifier: .gregorian)
    formatter.locale = Locale(identifier: "en_US_POSIX")
    formatter.timeZone = .current
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    return formatter
}()

private func parseInt(_ value: String?) throws -> Int? {
    guard let value else {
        return nil
    }
    guard let intValue = Int(value) else {
        throw CLIError("数值参数必须是整数。")
    }
    return intValue
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

    mutating func consumeFlag(_ name: String) -> Bool {
        guard let index = arguments.firstIndex(of: name) else {
            return false
        }
        arguments.remove(at: index)
        return true
    }

    func ensureNoUnusedArguments() throws {
        guard arguments.isEmpty else {
            throw CLIError("无法识别参数：\(arguments.joined(separator: " "))。")
        }
    }
}
