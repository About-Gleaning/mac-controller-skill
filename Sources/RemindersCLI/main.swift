import EventKit
import Foundation
import RemindersCore

let parser = CommandParser(arguments: Array(CommandLine.arguments.dropFirst()))

do {
    let command = try parser.parse()
    let controller = try RemindersController()
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

private final class RemindersController {
    private let store = EKEventStore()

    init() throws {
        try requestReminderAccess(store: store)
    }

    func run(_ command: Command) throws -> String {
        switch command {
        case .create(let options):
            return encodeSuccess(CreateData(reminder: try create(options)))
        case .list(let options):
            return encodeSuccess(try list(options))
        case .update(let options):
            try update(options)
            return encodeSuccess(UpdateData(id: options.id, updated: true))
        case .complete(let options):
            try complete(options)
            return encodeSuccess(CompleteData(id: options.id, completed: true))
        }
    }

    private func create(_ options: CreateOptions) throws -> ReminderOutput {
        let calendar = try targetCalendar(named: options.list)
        let reminder = EKReminder(eventStore: store)
        reminder.title = options.name
        reminder.calendar = calendar
        if let body = options.body {
            reminder.notes = body
        }
        if let due = options.due {
            reminder.dueDateComponents = Calendar.current.dateComponents(in: .current, from: due)
        }
        if let priority = options.priority {
            reminder.priority = priority
        }
        try store.save(reminder, commit: true)
        return output(for: reminder)
    }

    private func list(_ options: ListOptions) throws -> ListData {
        let calendars = try targetCalendars(named: options.list)
        let completed = options.completed ?? false
        let predicate: NSPredicate
        if completed {
            predicate = store.predicateForCompletedReminders(withCompletionDateStarting: nil, ending: nil, calendars: calendars)
        } else {
            predicate = store.predicateForIncompleteReminders(withDueDateStarting: nil, ending: nil, calendars: calendars)
        }

        let reminders = try fetchReminders(matching: predicate)
        let query = options.query?.lowercased()
        let probeLimit = options.offset + options.limit + 1
        var matched = 0
        var rows: [ReminderOutput] = []

        for reminder in reminders {
            if let query, !reminder.title.lowercased().contains(query) {
                continue
            }
            matched += 1
            if matched > options.offset && rows.count < options.limit {
                rows.append(output(for: reminder))
            }
            if matched >= probeLimit {
                break
            }
        }

        let hasMore = matched > options.offset + options.limit
        return ListData(
            reminders: rows,
            count: rows.count,
            offset: options.offset,
            limit: options.limit,
            hasMore: hasMore,
            nextOffset: hasMore ? options.offset + options.limit : nil
        )
    }

    private func update(_ options: UpdateOptions) throws {
        let reminder = try reminder(by: options.id)
        if let name = options.name {
            reminder.title = name
        }
        if let body = options.body {
            reminder.notes = body
        }
        if options.clearDue {
            reminder.dueDateComponents = nil
        } else if let due = options.due {
            reminder.dueDateComponents = Calendar.current.dateComponents(in: .current, from: due)
        }
        if let priority = options.priority {
            reminder.priority = priority
        }
        if let completed = options.completed {
            reminder.isCompleted = completed
        }
        try store.save(reminder, commit: true)
    }

    private func complete(_ options: CompleteOptions) throws {
        let reminder = try reminder(by: options.id)
        reminder.isCompleted = true
        try store.save(reminder, commit: true)
    }

    private func targetCalendar(named name: String?) throws -> EKCalendar {
        if let name {
            guard let calendar = store.calendars(for: .reminder).first(where: { $0.title == name }) else {
                throw CLIError("找不到提醒事项列表：\(name)。", code: 1)
            }
            return calendar
        }
        guard let calendar = store.defaultCalendarForNewReminders() else {
            throw CLIError("无法获取默认提醒事项列表。请确认提醒事项应用可用。", code: 1)
        }
        return calendar
    }

    private func targetCalendars(named name: String?) throws -> [EKCalendar]? {
        guard let name else {
            return nil
        }
        guard let calendar = store.calendars(for: .reminder).first(where: { $0.title == name }) else {
            throw CLIError("找不到提醒事项列表：\(name)。", code: 1)
        }
        return [calendar]
    }

    private func reminder(by id: String) throws -> EKReminder {
        guard let reminder = store.calendarItem(withIdentifier: id) as? EKReminder else {
            throw CLIError("找不到提醒事项：\(id)。", code: 1)
        }
        return reminder
    }

    private func fetchReminders(matching predicate: NSPredicate) throws -> [EKReminder] {
        let semaphore = DispatchSemaphore(value: 0)
        var fetched: [EKReminder]?
        store.fetchReminders(matching: predicate) { reminders in
            fetched = reminders
            semaphore.signal()
        }
        semaphore.wait()
        return fetched ?? []
    }

    private func output(for reminder: EKReminder) -> ReminderOutput {
        ReminderOutput(
            id: reminder.calendarItemIdentifier,
            name: reminder.title ?? "",
            list: reminder.calendar.title,
            body: reminder.notes,
            completed: reminder.isCompleted,
            dueDate: formatDate(reminder.dueDateComponents?.date),
            priority: reminder.priority
        )
    }
}

private func requestReminderAccess(store: EKEventStore) throws {
    let status = EKEventStore.authorizationStatus(for: .reminder)
    if isAuthorized(status) {
        return
    }
    if status == .denied || status == .restricted {
        throw CLIError("没有权限访问提醒事项。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 访问「提醒事项」。", code: 1)
    }

    let semaphore = DispatchSemaphore(value: 0)
    var granted = false
    var requestError: Error?
    if #available(macOS 14.0, *) {
        store.requestFullAccessToReminders { ok, error in
            granted = ok
            requestError = error
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .reminder) { ok, error in
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
        throw CLIError("没有权限访问提醒事项。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 访问「提醒事项」。", code: 1)
    }
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

private func normalizeError(_ error: Error) -> String {
    if let cliError = error as? CLIError {
        return cliError.message
    }
    let text = error.localizedDescription
    if text.localizedCaseInsensitiveContains("mach error") {
        return "无法连接提醒事项服务。请确认 Reminders 应用可用，并已授予当前终端或 Codex 访问「提醒事项」权限。"
    }
    return text.isEmpty ? "提醒事项操作失败。" : text
}
