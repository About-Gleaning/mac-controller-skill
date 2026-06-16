import Foundation

public let calendarDateFormatHint = "YYYY-MM-DD HH:MM:SS"
public let defaultEventListLimit = 20
public let maxUnscopedEventListLimit = 20
public let maxScopedEventListLimit = 50
public let maxEventListOffset = 500

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
    case create(CreateOptions)
    case list(ListOptions)
    case update(UpdateOptions)
    case delete(DeleteOptions)
}

public struct CreateOptions: Equatable {
    public var title: String
    public var calendar: String?
    public var start: Date
    public var end: Date
    public var allDay: Bool
    public var location: String?
    public var notes: String?
}

public struct ListOptions: Equatable {
    public var calendar: String?
    public var query: String?
    public var from: Date?
    public var to: Date?
    public var limit: Int
    public var offset: Int
}

public struct UpdateOptions: Equatable {
    public var id: String
    public var title: String?
    public var calendar: String?
    public var start: Date?
    public var end: Date?
    public var allDay: Bool?
    public var location: String?
    public var notes: String?
}

public struct DeleteOptions: Equatable {
    public var id: String
}

public struct EventOutput: Codable, Equatable {
    public var id: String
    public var title: String
    public var calendar: String
    public var startDate: String
    public var endDate: String
    public var allDay: Bool
    public var location: String?
    public var notes: String?

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case calendar
        case startDate = "start_date"
        case endDate = "end_date"
        case allDay = "all_day"
        case location
        case notes
    }

    public init(id: String, title: String, calendar: String, startDate: String, endDate: String, allDay: Bool, location: String?, notes: String?) {
        self.id = id
        self.title = title
        self.calendar = calendar
        self.startDate = startDate
        self.endDate = endDate
        self.allDay = allDay
        self.location = location
        self.notes = notes
    }
}

public struct CreateData: Codable, Equatable {
    public var event: EventOutput

    public init(event: EventOutput) {
        self.event = event
    }
}

public struct ListData: Codable, Equatable {
    public var events: [EventOutput]
    public var count: Int
    public var offset: Int
    public var limit: Int
    public var hasMore: Bool
    public var nextOffset: Int?

    enum CodingKeys: String, CodingKey {
        case events
        case count
        case offset
        case limit
        case hasMore = "has_more"
        case nextOffset = "next_offset"
    }

    public init(events: [EventOutput], count: Int, offset: Int, limit: Int, hasMore: Bool, nextOffset: Int?) {
        self.events = events
        self.count = count
        self.offset = offset
        self.limit = limit
        self.hasMore = hasMore
        self.nextOffset = nextOffset
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

public struct DeleteData: Codable, Equatable {
    public var id: String
    public var deleted: Bool

    public init(id: String, deleted: Bool) {
        self.id = id
        self.deleted = deleted
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

public struct EmptyData: Codable, Equatable {}

public final class CommandParser {
    private let arguments: [String]

    public init(arguments: [String]) {
        self.arguments = arguments
    }

    public func parse() throws -> Command {
        guard let command = arguments.first else {
            throw CLIError("必须提供命令：auth-status、request-access、create、list、update 或 delete。")
        }

        var reader = ArgumentReader(Array(arguments.dropFirst()))
        switch command {
        case "auth-status":
            try reader.ensureNoUnusedArguments()
            return .authStatus
        case "request-access":
            try reader.ensureNoUnusedArguments()
            return .requestAccess
        case "create":
            let title = try reader.requiredValue(for: "--title")
            let start = try reader.requiredDate(for: "--start")
            let end = try reader.requiredDate(for: "--end")
            let options = CreateOptions(
                title: title,
                calendar: try reader.optionalValue(for: "--calendar"),
                start: start,
                end: end,
                allDay: try parseBool(try reader.optionalValue(for: "--all-day")) ?? false,
                location: try reader.optionalValue(for: "--location"),
                notes: try reader.optionalValue(for: "--notes")
            )
            try validateDateRange(start: options.start, end: options.end)
            try reader.ensureNoUnusedArguments()
            return .create(options)
        case "list":
            let options = ListOptions(
                calendar: try reader.optionalValue(for: "--calendar"),
                query: try reader.optionalValue(for: "--query"),
                from: try parseDate(try reader.optionalValue(for: "--from")),
                to: try parseDate(try reader.optionalValue(for: "--to")),
                limit: try parseInt(try reader.optionalValue(for: "--limit")) ?? defaultEventListLimit,
                offset: try parseInt(try reader.optionalValue(for: "--offset")) ?? 0
            )
            try validateListOptions(options)
            try reader.ensureNoUnusedArguments()
            return .list(options)
        case "update":
            let start = try parseDate(try reader.optionalValue(for: "--start"))
            let end = try parseDate(try reader.optionalValue(for: "--end"))
            if let start, let end {
                try validateDateRange(start: start, end: end)
            }
            let options = UpdateOptions(
                id: try reader.requiredValue(for: "--id"),
                title: try reader.optionalValue(for: "--title"),
                calendar: try reader.optionalValue(for: "--calendar"),
                start: start,
                end: end,
                allDay: try parseBool(try reader.optionalValue(for: "--all-day")),
                location: try reader.optionalValue(for: "--location"),
                notes: try reader.optionalValue(for: "--notes")
            )
            try reader.ensureNoUnusedArguments()
            return .update(options)
        case "delete":
            let options = DeleteOptions(id: try reader.requiredValue(for: "--id"))
            try reader.ensureNoUnusedArguments()
            return .delete(options)
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
        throw CLIError("时间格式必须是 \(calendarDateFormatHint)。")
    }
    guard calendarDateFormatter.date(from: value) != nil else {
        throw CLIError("时间格式必须是 \(calendarDateFormatHint)。")
    }
    return calendarDateFormatter.date(from: value)
}

public func formatDate(_ date: Date?) -> String? {
    guard let date else {
        return nil
    }
    return calendarDateFormatter.string(from: date)
}

public func validateDateRange(start: Date, end: Date) throws {
    guard start < end else {
        throw CLIError("--end 必须晚于 --start。")
    }
}

public func validateListOptions(_ options: ListOptions) throws {
    guard options.limit > 0 else {
        throw CLIError("--limit 必须大于 0。")
    }
    guard options.offset >= 0 && options.offset <= maxEventListOffset else {
        throw CLIError("--offset 必须在 0 到 \(maxEventListOffset) 之间。")
    }
    if let from = options.from, let to = options.to {
        try validateDateRange(start: from, end: to)
    }
    let maxLimit = options.query == nil && options.calendar == nil ? maxUnscopedEventListLimit : maxScopedEventListLimit
    guard options.limit <= maxLimit else {
        throw CLIError("当前查询的 --limit 不能超过 \(maxLimit)。请使用 --query、--calendar 或 --offset 缩小范围。")
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
      calendar-cli auth-status
      calendar-cli request-access
      calendar-cli create --title 标题 --start "\(calendarDateFormatHint)" --end "\(calendarDateFormatHint)" [--calendar 日历] [--all-day true|false] [--location 地点] [--notes 备注]
      calendar-cli list [--calendar 日历] [--query 关键词] [--from "\(calendarDateFormatHint)"] [--to "\(calendarDateFormatHint)"] [--limit 数量] [--offset 数量]
      calendar-cli update --id ID [--title 标题] [--calendar 日历] [--start "\(calendarDateFormatHint)"] [--end "\(calendarDateFormatHint)"] [--all-day true|false] [--location 地点] [--notes 备注]
      calendar-cli delete --id ID
    """
}

private let calendarDateFormatter: DateFormatter = {
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

    mutating func requiredDate(for name: String) throws -> Date {
        guard let value = try optionalValue(for: name) else {
            throw CLIError("缺少必填参数 \(name)。")
        }
        return try parseDate(value)!
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
