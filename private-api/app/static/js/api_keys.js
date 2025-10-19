document.addEventListener('DOMContentLoaded', () => {
  const table = document.getElementById('api-keys-table');
  const csrfToken = table?.dataset.csrf || '';
  const form = document.getElementById('new-key-form');

  const renderRow = (key) => {
    const tr = document.createElement('tr');
    tr.dataset.keyId = key.id;
    tr.innerHTML = `
      <td>${key.label || `Key #${key.id}`}</td>
      <td class="monospace">${key.key}</td>
      <td>${key.usage_count ?? 0}</td>
      <td>${key.is_active ? 'Active' : 'Revoked'}</td>
      <td>${
        key.is_active
          ? '<button class="button danger revoke">Revoke</button>'
          : '<span class="tag">Revoked</span>'
      }</td>
    `;
    return tr;
  };

  const refreshEmptyState = () => {
    if (!table) return;
    const rows = table.querySelectorAll('tbody tr');
    if (rows.length === 0) {
      const empty = document.createElement('tr');
      empty.innerHTML = '<td colspan="5" class="empty">No API keys yet. Generate one below.</td>';
      table.querySelector('tbody').appendChild(empty);
    }
  };

  if (form) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = { label: formData.get('label') || null };
      try {
        const response = await fetch('/api_keys/new', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
          },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          throw new Error('Failed to create key');
        }
        const data = await response.json();
        const tbody = table.querySelector('tbody');
        tbody.innerHTML = '';
        tbody.appendChild(renderRow(data));
        form.reset();
      } catch (err) {
        console.error(err);
        alert('Unable to generate API key. Check console for details.');
      }
    });
  }

  if (table) {
    table.addEventListener('click', async (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      if (!target.classList.contains('revoke')) return;

      const row = target.closest('tr');
      const keyId = row?.dataset.keyId;
      if (!keyId) return;

      try {
        const response = await fetch(`/api_keys/revoke/${keyId}`, {
          method: 'POST',
          headers: {
            'X-CSRF-Token': csrfToken,
          },
        });
        if (!response.ok) {
          throw new Error('Failed to revoke key');
        }
        const data = await response.json();
        const replacement = renderRow(data);
        row.replaceWith(replacement);
      } catch (err) {
        console.error(err);
        alert('Unable to revoke API key.');
      }
    });
  }

  refreshEmptyState();
});
