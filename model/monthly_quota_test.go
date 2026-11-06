package model

import (
	"testing"

	"github.com/glebarez/sqlite"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"gorm.io/gorm"
)

func setupMonthlyQuotaDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err)
	require.NoError(t, db.AutoMigrate(&User{}))
	old := DB
	DB = db
	t.Cleanup(func() { DB = old })
	return db
}

func TestUserBeforeCreateMonthlyQuotaDefaults(t *testing.T) {
	db := setupMonthlyQuotaDB(t)

	// No explicit monthly quota: the default tier applies, quota stays 0 and
	// the stamp stays empty so the first read grants the first month.
	u := User{Username: "newbie", AffCode: "aff_n", Password: "x"}
	require.NoError(t, db.Create(&u).Error)
	assert.Equal(t, DefaultMonthlyQuota, u.MonthlyQuota)
	assert.Equal(t, 0, u.Quota)
	assert.Equal(t, "", u.QuotaResetMonth)

	// First read of an unstamped user grants the monthly allowance.
	MaybeResetMonthlyQuota(u.Id)
	got := User{}
	require.NoError(t, db.First(&got, "id = ?", u.Id).Error)
	assert.Equal(t, DefaultMonthlyQuota, got.Quota)
	assert.Equal(t, MonthlyQuotaResetStamp(), got.QuotaResetMonth)

	// Explicit tier flows through the same path.
	u2 := User{Username: "vip", AffCode: "aff_v", Password: "x", MonthlyQuota: 500000000}
	require.NoError(t, db.Create(&u2).Error)
	MaybeResetMonthlyQuota(u2.Id)
	got = User{}
	require.NoError(t, db.First(&got, "id = ?", u2.Id).Error)
	assert.Equal(t, 500000000, got.Quota)
}

func TestMaybeResetMonthlyQuota(t *testing.T) {
	db := setupMonthlyQuotaDB(t)

	heavy := User{Username: "heavy", AffCode: "aff_h", Password: "x", MonthlyQuota: 500000000, Quota: 123, QuotaResetMonth: "2000-01"}
	require.NoError(t, db.Create(&heavy).Error)
	root := User{Username: "root", AffCode: "aff_r", Password: "x", Quota: 777, QuotaResetMonth: "2000-01"}
	require.NoError(t, db.Create(&root).Error)
	fallback := User{Username: "fallback", AffCode: "aff_f", Password: "x", MonthlyQuota: 0, Quota: 42, QuotaResetMonth: "2000-01"}
	require.NoError(t, db.Create(&fallback).Error)

	MaybeResetMonthlyQuota(heavy.Id)
	MaybeResetMonthlyQuota(root.Id)
	MaybeResetMonthlyQuota(fallback.Id)

	got := User{}
	require.NoError(t, db.First(&got, "id = ?", heavy.Id).Error)
	assert.Equal(t, 500000000, got.Quota, "stale month should reset quota to monthly_quota")
	assert.Equal(t, MonthlyQuotaResetStamp(), got.QuotaResetMonth)

	got = User{}
	require.NoError(t, db.First(&got, "id = ?", root.Id).Error)
	assert.Equal(t, 777, got.Quota, "root must never be reset")

	got = User{}
	require.NoError(t, db.First(&got, "id = ?", fallback.Id).Error)
	assert.Equal(t, DefaultMonthlyQuota, got.Quota, "monthly_quota<=0 falls back to the default tier")

	// Same-month rerun must not touch a freshly granted allowance.
	require.NoError(t, db.Model(&User{}).Where("id = ?", heavy.Id).Update("quota", 11).Error)
	MaybeResetMonthlyQuota(heavy.Id)
	got = User{}
	require.NoError(t, db.First(&got, "id = ?", heavy.Id).Error)
	assert.Equal(t, 11, got.Quota, "second call in the same month is a no-op")
}

func TestEditWithTxUpdatesMonthlyQuota(t *testing.T) {
	db := setupMonthlyQuotaDB(t)
	u := User{Username: "editme", AffCode: "aff_e", Password: "x", MonthlyQuota: DefaultMonthlyQuota}
	require.NoError(t, db.Create(&u).Error)

	u.MonthlyQuota = 1000000000
	require.NoError(t, u.EditWithTx(db, false))

	var got User
	require.NoError(t, db.First(&got, "id = ?", u.Id).Error)
	assert.Equal(t, 1000000000, got.MonthlyQuota)
}
