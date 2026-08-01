import { toRaw } from 'vue'

/**
 * Invoke an action only when an Element Plus slot row is one of the objects
 * supplied to that table's strongly typed data array.
 *
 * Element Plus currently exposes table slot rows as DefaultRow. Vue may expose
 * the same row as either its raw object or a reactive/readonly proxy, so both
 * representations must resolve to the same page-local row before invoking the
 * action.
 */
export const invokeTableRowAction = <
  T extends object,
  Args extends readonly unknown[],
  Result
>(
  rows: readonly T[],
  row: unknown,
  action: (typedRow: T, ...args: Args) => Result,
  ...args: Args
): Result => {
  if (typeof row !== 'object' || row === null) {
    throw new TypeError(
      'Cannot invoke table row action: the slot row is not an object.'
    )
  }

  const rawRow = toRaw(row)
  const typedRow = rows.find(
    candidate => candidate === row || toRaw(candidate) === rawRow
  )
  if (!typedRow) {
    throw new Error(
      'Cannot invoke table row action: the slot row is not part of the provided table data.'
    )
  }

  return action(typedRow, ...args)
}
