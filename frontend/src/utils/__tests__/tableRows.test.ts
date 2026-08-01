import assert from 'node:assert/strict'
import test from 'node:test'
import { reactive, readonly } from 'vue'

import { invokeTableRowAction } from '../tableRows.ts'

test('invokes an action when the table stores a proxy and the slot exposes raw data', () => {
  const rawRow = { id: 'row-1' }
  const rows = reactive([rawRow])

  const result = invokeTableRowAction(rows, rawRow, row => row.id)

  assert.equal(result, 'row-1')
})

test('invokes an action when the table stores raw data and the slot exposes a proxy', () => {
  const rawRow = { id: 'row-2' }
  const slotRow = readonly(rawRow)

  const result = invokeTableRowAction([rawRow], slotRow, row => row.id)

  assert.equal(result, 'row-2')
})

test('forwards action arguments and return values', () => {
  const row = { id: 'row-3' }

  const result = invokeTableRowAction(
    [row],
    row,
    (typedRow, suffix: string) => `${typedRow.id}-${suffix}`,
    'done'
  )

  assert.equal(result, 'row-3-done')
})

test('rejects an unrelated slot row instead of silently dropping the action', () => {
  assert.throws(
    () => invokeTableRowAction([{ id: 'row-4' }], { id: 'row-4' }, row => row.id),
    /slot row is not part of the provided table data/
  )
})

test('rejects a non-object slot row with a descriptive error', () => {
  assert.throws(
    () => invokeTableRowAction([{ id: 'row-5' }], null, row => row.id),
    /slot row is not an object/
  )
})
