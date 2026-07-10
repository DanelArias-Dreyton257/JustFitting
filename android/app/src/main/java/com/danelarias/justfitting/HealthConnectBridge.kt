package com.danelarias.justfitting

import android.content.Context
import androidx.activity.result.contract.ActivityResultContract
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.aggregate.AggregationResultGroupedByPeriod
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.NutritionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.time.TimeRangeFilter
import androidx.health.connect.client.units.Energy
import androidx.health.connect.client.units.Mass
import kotlinx.coroutines.runBlocking
import java.time.LocalDate
import java.time.Period
import java.time.ZoneId

/**
 * Phase 7.3 (Health Connect bridge, see README) -- the only Kotlin file in
 * this app. connect-client's API is suspend-function-based; Kotlin doesn't
 * expose a supported way to build the Continuation a Java caller would need
 * to invoke a suspend function directly, so every call here is wrapped in
 * runBlocking and exposed as an ordinary synchronous method HealthSyncPlugin
 * .java (and MainActivity.java, for the permission contract) can call
 * directly. See variables.gradle's comment for why this one file breaks
 * from the rest of the app's plain-Java convention.
 *
 * Read-only throughout: this app only ever consumes readings Samsung Health
 * / Mi Fitness already wrote into Health Connect, never writes its own.
 */
object HealthConnectBridge {
    @JvmField
    val STEPS_PERMISSION: String = HealthPermission.getReadPermission(StepsRecord::class)

    @JvmField
    val NUTRITION_PERMISSION: String = HealthPermission.getReadPermission(NutritionRecord::class)

    // Without this, Health Connect silently clamps every read to the last
    // 30 days regardless of the requested range -- the real cause of a
    // reported bug where a >30-day "Sync last N days" value only ever
    // returned 30 days of readings. Not exposed as a typed constant on
    // this project's pinned 1.1.0-alpha08 connect-client (it only ships in
    // 1.1.0+), but it's a plain Health Connect provider-side permission
    // string, so it works fine requested/checked as a literal here.
    @JvmField
    val HISTORY_PERMISSION: String = "android.permission.health.READ_HEALTH_DATA_HISTORY"

    @JvmStatic
    fun allPermissions(): Set<String> = setOf(STEPS_PERMISSION, NUTRITION_PERMISSION, HISTORY_PERMISSION)

    // The strict minimum a sync actually needs -- unlike allPermissions()
    // (requested together for one system dialog), a user declining the
    // optional history permission shouldn't block Steps/Nutrition sync
    // entirely; Health Connect just keeps clamping reads to 30 days for
    // them, same as before this permission existed.
    @JvmStatic
    fun requiredPermissions(): Set<String> = setOf(STEPS_PERMISSION, NUTRITION_PERMISSION)

    // Re-exported so HealthSyncPlugin.java never has to reference
    // HealthConnectClient's own Companion object directly (Kotlin
    // companion access from Java is its own source of interop friction --
    // keeping all of it inside this one bridge file is the point).
    @JvmField
    val SDK_AVAILABLE: Int = HealthConnectClient.SDK_AVAILABLE

    @JvmField
    val SDK_UNAVAILABLE: Int = HealthConnectClient.SDK_UNAVAILABLE

    @JvmField
    val SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED: Int =
        HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED

    // Distinguishing these three lets the Settings UI point the user at
    // installing/updating Health Connect instead of a generic failure
    // (README's Phase 7.3 "Open risks" note).
    @JvmStatic
    fun sdkStatus(context: Context): Int = HealthConnectClient.getSdkStatus(context)

    @JvmStatic
    fun createPermissionRequestContract(): ActivityResultContract<Set<String>, Set<String>> =
        PermissionController.createRequestPermissionResultContract()

    @JvmStatic
    fun hasAllPermissions(context: Context, permissions: Set<String>): Boolean =
        grantedPermissions(context).containsAll(permissions)

    // Phase 7.5 (Settings UI, see README): the raw granted set, not just a
    // combined boolean -- Health Connect's own permission dialog lets the
    // user grant Steps and deny Nutrition (or vice versa), so the Settings
    // UI needs to show each source's status independently rather than one
    // all-or-nothing "connected".
    @JvmStatic
    fun grantedPermissions(context: Context): Set<String> = runBlocking {
        HealthConnectClient.getOrCreate(context).permissionController.getGrantedPermissions()
    }

    /**
     * Steps (Mi Fitness) and calories/macros (Samsung Health) for each
     * whole day in [sinceDate, untilDate) -- untilDate itself is excluded,
     * a plain half-open range with no "not today" meaning baked in here;
     * it's entirely up to the caller which day is last (HealthSyncPlugin.java
     * passes tomorrow, so today's still-accumulating total is included as
     * the final, partial day -- see its own comment, Phase 10.2). Uses
     * Health Connect's own per-day aggregation (aggregateGroupByPeriod)
     * rather than reading and summing raw records by hand, so a record
     * spanning midnight is attributed the same way Health Connect's own UI
     * would, and dataOriginFilter does the app-origin filtering
     * server-side instead of over-fetching every contributing app's data
     * first.
     */
    @JvmStatic
    fun readDailyReadings(
        context: Context,
        sinceDate: LocalDate,
        untilDate: LocalDate,
        stepsPackageNames: Set<String>,
        nutritionPackageNames: Set<String>,
    ): List<DailyReading> = runBlocking {
        val client = HealthConnectClient.getOrCreate(context)
        // aggregateGroupByPeriod (a calendar Period, not a fixed Duration)
        // requires a LocalDateTime-based TimeRangeFilter, not an
        // Instant-based one -- confirmed on a real device: the Instant
        // form fails at runtime with "Either use TimeRangeFilter with
        // LocalDateTime or AggregateGroupByDurationRequest", a constraint
        // enforced inside aggregateGroupByPeriod itself, not by the
        // compiler (TimeRangeFilter's type doesn't encode which
        // constructor built it).
        val range = TimeRangeFilter.between(
            sinceDate.atStartOfDay(),
            untilDate.atStartOfDay(),
        )

        val stepsByDay = mutableMapOf<LocalDate, Double>()
        if (stepsPackageNames.isNotEmpty()) {
            val stepsGroups = client.aggregateGroupByPeriod(
                AggregateGroupByPeriodRequest(
                    metrics = setOf(StepsRecord.COUNT_TOTAL),
                    timeRangeFilter = range,
                    timeRangeSlicer = Period.ofDays(1),
                    dataOriginFilter = stepsPackageNames.map { PackageOrigin(it) }.toSet(),
                )
            )
            for (group in stepsGroups) {
                val day = group.startTime.toLocalDate()
                group.result[StepsRecord.COUNT_TOTAL]?.let { stepsByDay[day] = it.toDouble() }
            }
        }

        val caloriesByDay = mutableMapOf<LocalDate, Double>()
        val carbsByDay = mutableMapOf<LocalDate, Double>()
        val fatByDay = mutableMapOf<LocalDate, Double>()
        val proteinByDay = mutableMapOf<LocalDate, Double>()
        if (nutritionPackageNames.isNotEmpty()) {
            val nutritionGroups = client.aggregateGroupByPeriod(
                AggregateGroupByPeriodRequest(
                    metrics = setOf(
                        NutritionRecord.ENERGY_TOTAL,
                        NutritionRecord.TOTAL_CARBOHYDRATE_TOTAL,
                        NutritionRecord.TOTAL_FAT_TOTAL,
                        NutritionRecord.PROTEIN_TOTAL,
                    ),
                    timeRangeFilter = range,
                    timeRangeSlicer = Period.ofDays(1),
                    dataOriginFilter = nutritionPackageNames.map { PackageOrigin(it) }.toSet(),
                )
            )
            for (group in nutritionGroups) {
                val day = group.startTime.toLocalDate()
                val energy: Energy? = group.result[NutritionRecord.ENERGY_TOTAL]
                val carbs: Mass? = group.result[NutritionRecord.TOTAL_CARBOHYDRATE_TOTAL]
                val fat: Mass? = group.result[NutritionRecord.TOTAL_FAT_TOTAL]
                val protein: Mass? = group.result[NutritionRecord.PROTEIN_TOTAL]
                energy?.let { caloriesByDay[day] = it.inKilocalories }
                carbs?.let { carbsByDay[day] = it.inGrams }
                fat?.let { fatByDay[day] = it.inGrams }
                protein?.let { proteinByDay[day] = it.inGrams }
            }
        }

        val allDays = stepsByDay.keys + caloriesByDay.keys + carbsByDay.keys + fatByDay.keys + proteinByDay.keys
        allDays.sorted().map { day ->
            DailyReading(
                date = day.toString(),
                steps = stepsByDay[day],
                intakeKcal = caloriesByDay[day],
                carbsG = carbsByDay[day],
                fatG = fatByDay[day],
                proteinG = proteinByDay[day],
            )
        }
    }

    private fun PackageOrigin(packageName: String) =
        androidx.health.connect.client.records.metadata.DataOrigin(packageName)
}

data class DailyReading(
    val date: String,
    val steps: Double?,
    val intakeKcal: Double?,
    val carbsG: Double?,
    val fatG: Double?,
    val proteinG: Double?,
)
