/**
 * Invoke an action only when an Element Plus slot row is one of the objects
 * supplied to that table's strongly typed data array.
 *
 * Element Plus currently exposes table slot rows as DefaultRow. Object
 * identity provides a runtime proof of the page-local row type without a cast.
 */
export const invokeTableRowAction = <
  T extends object,
  Args extends readonly unknown[]
>(
  rows: readonly T[],
  row: unknown,
  action: (typedRow: T, ...args: Args) => unknown,
  ...args: Args
): void => {
  const typedRow = rows.find(candidate => candidate === row)
  if (typedRow) {
    void action(typedRow, ...args)
  }
}
