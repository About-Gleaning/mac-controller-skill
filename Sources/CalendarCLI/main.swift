import CalendarCore
import EventKit
import Foundation

let parser = CommandParser(arguments: Array(CommandLine.arguments.dropFirst()))

do {
    let command = try parser.parse()
    let controller = CalendarController()
    let output = try controller.run(command)
    print(output)
} catch let error as CLIError {
    if error.code == 0 {
        print(error.message)
    } else {
        print(encodeFailure(message: error.message))
    }
    exit(error.code)
} catch {
    print(encodeFailure(message: normalizeError(error)))
    exit(1)
}

private final class CalendarController {
    private let store = EKEventStore()

    func run(_ command: Command) throws -> String {
        switch command {
        case .authStatus:
            return encodeSuccess(authStatusData())
        case .requestAccess:
            return encodeSuccess(try requestAccessData())
        case .create(let options):
            try ensureEventAccess(store: store)
            return encodeSuccess(CreateData(event: try create(options)))
        case .list(let options):
            try ensureEventAccess(store: store)
            return encodeSuccess(try list(options))
        case .update(let options):
            try ensureEventAccess(store: store)
            try update(options)
            return encodeSuccess(UpdateData(id: options.id, updated: true))
        case .delete(let options):
            try ensureEventAccess(store: store)
            try delete(options)
            return encodeSuccess(DeleteData(id: options.id, deleted: true))
        }
    }

    private func authStatusData() -> AuthStatusData {
        calendarAuthData(for: EKEventStore.authorizationStatus(for: .event))
    }

    private func requestAccessData() throws -> RequestAccessData {
        let granted = try requestEventAccess(store: store)
        let statusData = calendarAuthData(for: EKEventStore.authorizationStatus(for: .event))
        return RequestAccessData(
            service: statusData.service,
            granted: granted,
            status: statusData.status,
            message: statusData.message,
            nextSteps: statusData.nextSteps
        )
    }

    private func create(_ options: CreateOptions) throws -> EventOutput {
        let event = EKEvent(eventStore: store)
        event.title = options.title
        event.calendar = try targetCalendar(named: options.calendar)
        event.startDate = options.start
        event.endDate = options.end
        event.isAllDay = options.allDay
        event.location = options.location
        event.notes = options.notes
        try store.save(event, span: .thisEvent, commit: true)
        return output(for: event)
    }

    private func list(_ options: ListOptions) throws -> ListData {
        let range = defaultedRange(from: options.from, to: options.to)
        let calendars = try targetCalendars(named: options.calendar)
        let predicate = store.predicateForEvents(withStart: range.start, end: range.end, calendars: calendars)
        let events = store.events(matching: predicate).sorted { $0.startDate < $1.startDate }
        let query = options.query?.lowercased()
        let probeLimit = options.offset + options.limit + 1
        var matched = 0
        var rows: [EventOutput] = []

        for event in events {
            if let query, !matches(event: event, query: query) {
                continue
            }
            matched += 1
            if matched > options.offset && rows.count < options.limit {
                rows.append(output(for: event))
            }
            if matched >= probeLimit {
                break
            }
        }

        let hasMore = matched > options.offset + options.limit
        return ListData(
            events: rows,
            count: rows.count,
            offset: options.offset,
            limit: options.limit,
            hasMore: hasMore,
            nextOffset: hasMore ? options.offset + options.limit : nil
        )
    }

    private func update(_ options: UpdateOptions) throws {
        let event = try event(by: options.id)
        if let title = options.title {
            event.title = title
        }
        if let calendar = options.calendar {
            event.calendar = try targetCalendar(named: calendar)
        }
        if let start = options.start {
            event.startDate = start
        }
        if let end = options.end {
            event.endDate = end
        }
        try validateDateRange(start: event.startDate, end: event.endDate)
        if let allDay = options.allDay {
            event.isAllDay = allDay
        }
        if let location = options.location {
            event.location = location
        }
        if let notes = options.notes {
            event.notes = notes
        }
        try store.save(event, span: .thisEvent, commit: true)
    }

    private func delete(_ options: DeleteOptions) throws {
        let event = try event(by: options.id)
        try store.remove(event, span: .thisEvent, commit: true)
    }

    private func targetCalendar(named name: String?) throws -> EKCalendar {
        if let name {
            guard let calendar = store.calendars(for: .event).first(where: { $0.title == name }) else {
                throw CLIError("找不到日历：\(name)。", code: 1)
            }
            return calendar
        }
        guard let calendar = store.defaultCalendarForNewEvents else {
            throw CLIError("无法获取默认日历。请确认日历应用可用。", code: 1)
        }
        return calendar
    }

    private func targetCalendars(named name: String?) throws -> [EKCalendar]? {
        guard let name else {
            return nil
        }
        guard let calendar = store.calendars(for: .event).first(where: { $0.title == name }) else {
            throw CLIError("找不到日历：\(name)。", code: 1)
        }
        return [calendar]
    }

    private func event(by id: String) throws -> EKEvent {
        guard let event = store.event(withIdentifier: id) else {
            throw CLIError("找不到日程：\(id)。", code: 1)
        }
        return event
    }

    private func defaultedRange(from: Date?, to: Date?) -> (start: Date, end: Date) {
        if let from, let to {
            return (from, to)
        }
        if let from {
            return (from, Calendar.current.date(byAdding: .day, value: 30, to: from)!)
        }
        if let to {
            return (Calendar.current.date(byAdding: .day, value: -30, to: to)!, to)
        }

        // 无边界查询默认覆盖今天起 30 天，贴近日常查看近期日程的场景，同时限制本机数据扫描范围。
        let start = Calendar.current.startOfDay(for: Date())
        return (start, Calendar.current.date(byAdding: .day, value: 30, to: start)!)
    }

    private func matches(event: EKEvent, query: String) -> Bool {
        if event.title.lowercased().contains(query) {
            return true
        }
        if event.location?.lowercased().contains(query) == true {
            return true
        }
        return event.notes?.lowercased().contains(query) == true
    }

    private func output(for event: EKEvent) -> EventOutput {
        EventOutput(
            id: event.eventIdentifier,
            title: event.title ?? "",
            calendar: event.calendar.title,
            startDate: formatDate(event.startDate) ?? "",
            endDate: formatDate(event.endDate) ?? "",
            allDay: event.isAllDay,
            location: event.location,
            notes: event.notes
        )
    }
}

@discardableResult
private func requestEventAccess(store: EKEventStore) throws -> Bool {
    let status = EKEventStore.authorizationStatus(for: .event)
    if isAuthorized(status) {
        return true
    }
    if status == .denied || status == .restricted {
        throw CLIError(calendarAuthData(for: status).message, code: 1)
    }

    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    var requestError: Error?
    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { ok, error in
            granted = ok
            requestError = error
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .event) { ok, error in
            granted = ok
            requestError = error
            semaphore.signal()
        }
    }
    semaphore.wait()

    if let requestError {
        throw requestError
    }
    if !granted {
        throw CLIError(calendarAuthData(for: EKEventStore.authorizationStatus(for: .event)).message, code: 1)
    }
    return granted
}

private func ensureEventAccess(store: EKEventStore) throws {
    try requestEventAccess(store: store)
}

private func isAuthorized(_ status: EKAuthorizationStatus) -> Bool {
    if status == .authorized {
        return true
    }
    if #available(macOS 14.0, *) {
        return status == .fullAccess
    }
    return false
}

private func statusName(_ status: EKAuthorizationStatus) -> String {
    switch status {
    case .notDetermined:
        return "not_determined"
    case .restricted:
        return "restricted"
    case .denied:
        return "denied"
    case .authorized:
        return "authorized"
    case .writeOnly:
        return "write_only"
    case .fullAccess:
        return "full_access"
    @unknown default:
        return "unknown"
    }
}

private func calendarAuthData(for status: EKAuthorizationStatus) -> AuthStatusData {
    let name = statusName(status)
    let authorized = isAuthorized(status)
    let steps = [
        "到「系统设置 > 隐私与安全性 > 日历」允许当前运行的 Codex、CodePilot 或终端访问日历。",
        "如果系统不再弹出授权窗口，可手动执行：tccutil reset Calendar，然后重新运行 request-access。",
        "授权后重新运行原日历命令。",
    ]

    let message: String
    switch status {
    case .notDetermined:
        message = "日历权限尚未请求。请运行 request-access 触发系统授权窗口。"
    case .restricted:
        message = "日历访问被系统策略限制，当前进程无法请求权限。"
    case .denied:
        message = "没有权限访问日历。请到「系统设置 > 隐私与安全性 > 日历」允许当前运行的 Codex、CodePilot 或终端访问「日历」。"
    case .authorized, .fullAccess:
        message = "当前进程已获得日历完整访问权限。"
    case .writeOnly:
        message = "当前进程只有日历写入权限，无法查询或更新已有日程。请授予完整访问权限。"
    @unknown default:
        message = "当前日历权限状态未知，请到系统设置检查日历访问权限。"
    }

    return AuthStatusData(
        service: "calendar",
        status: name,
        authorized: authorized,
        message: message,
        nextSteps: authorized ? [] : steps
    )
}

private func normalizeError(_ error: Error) -> String {
    if let cliError = error as? CLIError {
        return cliError.message
    }
    let text = error.localizedDescription
    if text.localizedCaseInsensitiveContains("mach error") {
        return "无法连接日历服务。请确认 Calendar 应用可用，并已授予当前终端或 Codex 访问「日历」权限。"
    }
    return text.isEmpty ? "日历操作失败。" : text
}
