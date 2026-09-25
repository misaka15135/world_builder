using System;
using System.IO;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;

public static class WorldBuilderCityV3NavBuilder
{
    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
        public string adapter_version;
    }

    [Serializable] private sealed class Result
    {
        public string status = "failed";
        public string unity_version;
        public string navigation_package = "com.unity.ai.navigation@2.0.14";
        public string source_world_id;
        public string source_revision_id;
        public string scene_path;
        public string navmesh_asset_path;
        public string source_policy = "road_*, access_*, and bridge_main render meshes only";
        public int road_pieces;
        public int access_pieces;
        public int bridge_pieces;
        public int marked_meshes;
        public int agent_type_id;
        public float agent_radius_m;
        public float agent_height_m;
        public string west_to_east_path;
        public float path_length_m;
        public Vector3[] path_corners;
        public string error;
    }

    [Serializable] private sealed class ReopenResult
    {
        public string status = "failed";
        public string unity_version;
        public string scene_path = Base + "CityChunkNavigation.unity";
        public string navmesh_asset_path = Base + "CityChunkRoadsAndBridgeNavMesh.asset";
        public string path_status;
        public float path_length_m;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderCity/v3/";

    [MenuItem("World Builder/Validate Saved Chunked City Navigation v3")]
    public static void ValidateSaved()
    {
        var result = new ReopenResult { unity_version = Application.unityVersion };
        try
        {
            EditorSceneManager.OpenScene(result.scene_path, OpenSceneMode.Single);
            var surface = UnityEngine.Object.FindFirstObjectByType<NavMeshSurface>();
            var asset = AssetDatabase.LoadAssetAtPath<NavMeshData>(result.navmesh_asset_path);
            if (surface == null || asset == null || surface.navMeshData != asset ||
                surface.collectObjects != CollectObjects.MarkedWithModifier)
                throw new InvalidOperationException("saved scene has no matching road/bridge NavMesh asset");
            NavMeshHit west;
            NavMeshHit east;
            if (!NavMesh.SamplePosition(new Vector3(244f, 2f, 271f), out west, 1f, NavMesh.AllAreas) ||
                !NavMesh.SamplePosition(new Vector3(268f, 2f, 271f), out east, 1f, NavMesh.AllAreas))
                throw new InvalidOperationException("saved NavMesh has no west/east road points");
            var path = new NavMeshPath();
            var found = NavMesh.CalculatePath(west.position, east.position, NavMesh.AllAreas, path);
            result.path_status = path.status.ToString();
            if (!found || path.status != NavMeshPathStatus.PathComplete)
                throw new InvalidOperationException("saved NavMesh has no complete cross-bridge path");
            for (var i = 1; i < path.corners.Length; i++)
                result.path_length_m += Vector3.Distance(path.corners[i - 1], path.corners[i]);
            if (result.path_length_m < 22f || result.path_length_m > 35f)
                throw new InvalidOperationException("saved NavMesh path length changed");
            result.status = "pass";
            Debug.Log("WorldBuilder saved city v3 navigation validated: " + result.path_length_m + " m");
        }
        catch (Exception exception)
        {
            result.error = exception.ToString();
            Debug.LogException(exception);
            WriteReopenResult(result);
            throw;
        }
        WriteReopenResult(result);
    }

    [MenuItem("World Builder/Build Chunked City Navigation v3")]
    public static void Build()
    {
        var result = new Result
        {
            unity_version = Application.unityVersion,
            scene_path = Base + "CityChunkNavigation.unity",
            navmesh_asset_path = Base + "CityChunkRoadsAndBridgeNavMesh.asset"
        };
        try
        {
            WorldBuilderCityV3Builder.Build();
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(
                Application.dataPath, "WorldBuilderCity", "v3", "manifest.json")));
            if (manifest == null || manifest.adapter_version != "0.1.0-city.3")
                throw new InvalidOperationException("city v3 navigation manifest mismatch");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;

            var surfaceObject = new GameObject("Road and bridge navigation");
            var surface = surfaceObject.AddComponent<NavMeshSurface>();
            surface.collectObjects = CollectObjects.MarkedWithModifier;
            surface.useGeometry = NavMeshCollectGeometry.RenderMeshes;
            surface.defaultArea = NavMesh.GetAreaFromName("Walkable");
            var settings = NavMesh.GetSettingsByIndex(0);
            if (settings.agentTypeID < 0)
                throw new InvalidOperationException("no Unity NavMesh agent settings");
            surface.agentTypeID = settings.agentTypeID;
            result.agent_type_id = settings.agentTypeID;
            result.agent_radius_m = settings.agentRadius;
            result.agent_height_m = settings.agentHeight;

            foreach (var source in UnityEngine.Object.FindObjectsByType<WorldBuilderSourceId>(FindObjectsSortMode.None))
            {
                var isRoad = source.sourceId.StartsWith("road_", StringComparison.Ordinal);
                var isAccess = source.sourceId.StartsWith("access_", StringComparison.Ordinal);
                var isBridge = source.sourceId == "bridge_main";
                if (!isRoad && !isAccess && !isBridge) continue;
                var filters = source.GetComponentsInChildren<MeshFilter>(true);
                if (filters.Length != 1 || filters[0].sharedMesh == null)
                    throw new InvalidOperationException("navigation source has no single mesh: " + source.sourceId);
                var modifier = filters[0].gameObject.AddComponent<NavMeshModifier>();
                modifier.applyToChildren = false;
                result.marked_meshes++;
                if (isRoad) result.road_pieces++;
                if (isAccess) result.access_pieces++;
                if (isBridge) result.bridge_pieces++;
            }
            if (result.road_pieces != 44 || result.access_pieces != 90 || result.bridge_pieces != 2 ||
                result.marked_meshes != result.road_pieces + result.access_pieces + result.bridge_pieces)
                throw new InvalidOperationException("road/bridge navigation source count changed");

            surface.BuildNavMesh();
            if (surface.navMeshData == null)
                throw new InvalidOperationException("Unity returned no NavMeshData");
            var oldAsset = AssetDatabase.LoadAssetAtPath<NavMeshData>(result.navmesh_asset_path);
            if (oldAsset != null && !AssetDatabase.DeleteAsset(result.navmesh_asset_path))
                throw new InvalidOperationException("could not replace navigation asset");
            AssetDatabase.CreateAsset(surface.navMeshData, result.navmesh_asset_path);
            AssetDatabase.SaveAssets();

            NavMeshHit west;
            NavMeshHit east;
            if (!NavMesh.SamplePosition(new Vector3(244f, 2f, 271f), out west, 1f, NavMesh.AllAreas) ||
                !NavMesh.SamplePosition(new Vector3(268f, 2f, 271f), out east, 1f, NavMesh.AllAreas))
                throw new InvalidOperationException("west/east road has no NavMesh point");
            var path = new NavMeshPath();
            var found = NavMesh.CalculatePath(west.position, east.position, NavMesh.AllAreas, path);
            result.west_to_east_path = path.status.ToString();
            result.path_corners = path.corners;
            if (!found || path.status != NavMeshPathStatus.PathComplete || path.corners.Length < 2)
                throw new InvalidOperationException("west-to-east road path is incomplete");
            var crossedBridge = false;
            for (var i = 1; i < path.corners.Length; i++)
            {
                var a = path.corners[i - 1];
                var b = path.corners[i];
                result.path_length_m += Vector3.Distance(a, b);
                if (Mathf.Abs(b.x - a.x) > 0.001f &&
                    ((a.x <= 256f && b.x >= 256f) || (a.x >= 256f && b.x <= 256f)))
                {
                    var fraction = (256f - a.x) / (b.x - a.x);
                    if (Mathf.Lerp(a.z, b.z, fraction) >= 268f &&
                        Mathf.Lerp(a.z, b.z, fraction) <= 274f)
                        crossedBridge = true;
                }
            }
            if (!crossedBridge || result.path_length_m < 22f || result.path_length_m > 35f)
                throw new InvalidOperationException("path misses bridge or has unexpected length");

            EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), result.scene_path);
            AssetDatabase.SaveAssets();
            result.status = "pass";
            Debug.Log("WorldBuilder city v3 navigation built: " + result.marked_meshes +
                " meshes, complete path " + result.path_length_m + " m, scene " + result.scene_path);
        }
        catch (Exception exception)
        {
            result.error = exception.ToString();
            Debug.LogException(exception);
            WriteResult(result);
            throw;
        }
        WriteResult(result);
    }

    private static void WriteResult(Result result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V3_NAV_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v3-navigation-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }

    private static void WriteReopenResult(ReopenResult result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V3_NAV_REOPEN_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v3-navigation-reopen-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
