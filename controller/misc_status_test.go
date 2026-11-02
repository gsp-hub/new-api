/*
Copyright (C) 2023-2026 QuantumNous

This program is licensed under the GNU Affero General Public License as
published by the Free Software Foundation. See the LICENSE file for details.
*/
package controller

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/QuantumNous/new-api/common"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func getStatusPayload(t *testing.T, authedUserID int) map[string]any {
	t.Helper()
	response := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(response)
	context.Request = httptest.NewRequest(http.MethodGet, "/api/status", nil)
	if authedUserID > 0 {
		context.Set("id", authedUserID)
	}

	GetStatus(context)

	var payload struct {
		Success bool           `json:"success"`
		Data    map[string]any `json:"data"`
	}
	require.NoError(t, common.Unmarshal(response.Body.Bytes(), &payload))
	require.True(t, payload.Success)
	return payload.Data
}

func TestGetStatusHidesStorefrontFieldsFromAnonymousVisitors(t *testing.T) {
	gin.SetMode(gin.TestMode)

	anonymous := getStatusPayload(t, 0)
	for _, key := range anonymousHiddenStatusKeys {
		assert.NotContains(t, anonymous, key, "anonymous /api/status must not expose %s", key)
	}
	for _, key := range []string{"system_name", "logo", "register_enabled", "turnstile_check", "docs_link"} {
		assert.Contains(t, anonymous, key, "login page still needs %s", key)
	}

	authed := getStatusPayload(t, 1)
	for _, key := range anonymousHiddenStatusKeys {
		assert.Contains(t, authed, key, "authenticated /api/status must keep %s", key)
	}
}
