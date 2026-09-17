export function createPendingRow(row) {
  return {
    ...row,
    _pending: true,
    _pendingLabel: "Saving...",
    _clientId: row._clientId ?? crypto.randomUUID(),
  };
}

export function replacePendingRow(rows, clientId, confirmedRow) {
  return rows.map((row) => (row._clientId === clientId ? confirmedRow : row));
}

export function removePendingRow(rows, clientId) {
  return rows.filter((row) => row._clientId !== clientId);
}
