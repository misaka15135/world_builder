using System;
using System.IO;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;

public static class WorldBuilderCityV2InteriorNavBuilder
{
    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
        public string adapter_version;
        public string unity_version;
    }

    [Serializable] private sealed class Result
    {
        public string status = "failed";
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string source_building_id = "building_000";
        public string scene_path = Base + "CityInteriorNavigation.unity";
        public string navmesh_asset_path = Base + "CityInterior000NavMesh.asset";
        public string source_policy = "access_000, storey_000_*, stair_000, building_000 walls/lintel";
        public int access_meshes;
        public int floor_meshes;
        public int stair_meshes;
        public int blocked_wall_meshes;
        public int agent_type_id;
        public float agent_radius_m;
        public float agent_height_m;
        public float voxel_size_m;
        public bool east_door_link;
        public string start_to_room_path;
        public string[] checkpoint_paths;
        public Vector3[] direct_path_corners;
        public float direct_path_length_m;
        public bool crosses_east_door;
        public bool ascends_stair;
        public string error;
    }

    [Serializable] private sealed class ReopenResult
    {
        public string status = "failed";
        public string unity_version;
        public string scene_path = Base + "CityInteriorNavigation.unity";
        public string navmesh_asset_path = Base + "CityInterior000NavMesh.asset";
        public bool east_door_link;
        public string start_to_room_path;
        public float direct_path_length_m;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderCity/v2/";
    private static readonly Vector3[] Checkpoints = {
        new Vector3(34f, 2f, 16.5f),
        new Vector3(31f, 2.2f, 16.5f),
        new Vector3(28f, 2.2f, 17.1f),
        new Vector3(28f, 5.2f, 26f),
        new Vector3(25.5f, 5.2f, 26f)
    };

    [MenuItem("World Builder/Validate Saved First City Interior Navigation v2")]
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
                throw new InvalidOperationException("saved interior scene has no matching NavMesh asset");
            var links = UnityEngine.Object.FindObjectsByType<NavMeshLink>(FindObjectsSortMode.None);
            if (links.Length != 1 || !links[0].bidirectional ||
                Vector3.Distance(links[0].startPoint, new Vector3(33f, 2f, 16.5f)) > 0.01f ||
                Vector3.Distance(links[0].endPoint, new Vector3(31f, 2.2f, 16.5f)) > 0.01f)
                throw new InvalidOperationException("saved east door NavMeshLink is missing or changed");
            result.east_door_link = true;
            NavMeshHit start;
            NavMeshHit goal;
            if (!NavMesh.SamplePosition(Checkpoints[0], out start, 0.6f, NavMesh.AllAreas) ||
                !NavMesh.SamplePosition(Checkpoints[Checkpoints.Length - 1], out goal, 0.6f, NavMesh.AllAreas))
                throw new InvalidOperationException("saved interior NavMesh lacks start or room");
            var path = new NavMeshPath();
            var found = NavMesh.CalculatePath(start.position, goal.position, NavMesh.AllAreas, path);
            result.start_to_room_path = path.status.ToString();
            if (!found || path.status != NavMeshPathStatus.PathComplete)
                throw new InvalidOperationException("saved interior path is incomplete");
            for (var i = 1; i < path.corners.Length; i++)
                result.direct_path_length_m += Vector3.Distance(path.corners[i - 1], path.corners[i]);
            if (result.direct_path_length_m < 15f || result.direct_path_length_m > 25f)
                throw new InvalidOperationException("saved interior path length changed");
            result.status = "pass";
            Debug.Log("WorldBuilder saved first interior navigation validated: " +
                result.direct_path_length_m + " m");
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

    [MenuItem("World Builder/Build First City Interior Navigation v2")]
    public static void Build()
    {
        var result = new Result { unity_version = Application.unityVersion,
            checkpoint_paths = new string[Checkpoints.Length - 1] };
        try
        {
            EditorSceneManager.OpenScene(Base + "CityInteriors.unity", OpenSceneMode.Single);
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(Path.Combine(
                Application.dataPath, "WorldBuilderCity", "v2", "manifest.json")));
            if (manifest == null || manifest.adapter_version != "0.1.0-city.2" ||
                manifest.unity_version != Application.unityVersion)
                throw new InvalidOperationException("city v2 interior navigation manifest mismatch");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;

            var navRoot = new GameObject("Building 000 interior navigation");
            var surface = navRoot.AddComponent<NavMeshSurface>();
            surface.collectObjects = CollectObjects.MarkedWithModifier;
            surface.useGeometry = NavMeshCollectGeometry.RenderMeshes;
            surface.defaultArea = NavMesh.GetAreaFromName("Walkable");
            surface.overrideVoxelSize = true;
            surface.voxelSize = 0.05f;
            result.voxel_size_m = surface.voxelSize;
            var settings = NavMesh.GetSettingsByIndex(0);
            if (settings.agentTypeID < 0)
                throw new InvalidOperationException("no Unity NavMesh agent settings");
            surface.agentTypeID = settings.agentTypeID;
            result.agent_type_id = settings.agentTypeID;
            result.agent_radius_m = settings.agentRadius;
            result.agent_height_m = settings.agentHeight;

            foreach (var source in UnityEngine.Object.FindObjectsByType<WorldBuilderSourceId>(FindObjectsSortMode.None))
            {
                var id = source.sourceId;
                var isAccess = id == "access_000";
                var isFloor = id == "storey_000_0" || id == "storey_000_1";
                var isStair = id == "stair_000";
                var isWall = id == "building_000" &&
                    (source.name.Contains("wall") || source.name.Contains("lintel"));
                if (!isAccess && !isFloor && !isStair && !isWall) continue;
                var filters = source.GetComponentsInChildren<MeshFilter>(true);
                if (filters.Length != 1 || filters[0].sharedMesh == null)
                    throw new InvalidOperationException("interior nav source has no single mesh: " + source.name);
                var modifier = filters[0].gameObject.AddComponent<NavMeshModifier>();
                modifier.applyToChildren = false;
                if (isWall)
                {
                    modifier.overrideArea = true;
                    modifier.area = NavMesh.GetAreaFromName("Not Walkable");
                    result.blocked_wall_meshes++;
                }
                else if (isAccess) result.access_meshes++;
                else if (isFloor) result.floor_meshes++;
                else if (isStair) result.stair_meshes++;
            }
            if (result.access_meshes != 1 || result.floor_meshes != 5 ||
                result.stair_meshes != 21 || result.blocked_wall_meshes != 6)
                throw new InvalidOperationException("first interior navigation source count changed");

            surface.BuildNavMesh();
            if (surface.navMeshData == null)
                throw new InvalidOperationException("Unity returned no interior NavMeshData");
            var doorLink = new GameObject("Building 000 east door navigation link")
                .AddComponent<NavMeshLink>();
            doorLink.agentTypeID = settings.agentTypeID;
            doorLink.startPoint = new Vector3(33f, 2f, 16.5f);
            doorLink.endPoint = new Vector3(31f, 2.2f, 16.5f);
            doorLink.width = 1.2f;
            doorLink.bidirectional = true;
            result.east_door_link = true;
            var oldAsset = AssetDatabase.LoadAssetAtPath<NavMeshData>(result.navmesh_asset_path);
            if (oldAsset != null && !AssetDatabase.DeleteAsset(result.navmesh_asset_path))
                throw new InvalidOperationException("could not replace interior navigation asset");
            AssetDatabase.CreateAsset(surface.navMeshData, result.navmesh_asset_path);
            AssetDatabase.SaveAssets();
            EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), result.scene_path);

            var samples = new NavMeshHit[Checkpoints.Length];
            for (var i = 0; i < Checkpoints.Length; i++)
                if (!NavMesh.SamplePosition(Checkpoints[i], out samples[i], 0.6f, NavMesh.AllAreas))
                    throw new InvalidOperationException("no NavMesh at interior checkpoint " + i);
            for (var i = 1; i < samples.Length; i++)
            {
                var leg = new NavMeshPath();
                var found = NavMesh.CalculatePath(samples[i - 1].position,
                    samples[i].position, NavMesh.AllAreas, leg);
                result.checkpoint_paths[i - 1] = leg.status.ToString();
                if (!found || leg.status != NavMeshPathStatus.PathComplete)
                    throw new InvalidOperationException("incomplete interior checkpoint path " + (i - 1));
            }
            var direct = new NavMeshPath();
            var complete = NavMesh.CalculatePath(samples[0].position,
                samples[samples.Length - 1].position, NavMesh.AllAreas, direct);
            result.start_to_room_path = direct.status.ToString();
            result.direct_path_corners = direct.corners;
            if (!complete || direct.status != NavMeshPathStatus.PathComplete)
                throw new InvalidOperationException("start-to-room NavMesh path incomplete");
            for (var i = 1; i < direct.corners.Length; i++)
            {
                var a = direct.corners[i - 1];
                var b = direct.corners[i];
                result.direct_path_length_m += Vector3.Distance(a, b);
                if (a.x >= 32f && b.x <= 32f && Mathf.Abs(a.x - b.x) > 0.001f)
                {
                    var z = Mathf.Lerp(a.z, b.z, (32f - a.x) / (b.x - a.x));
                    if (z >= 16f && z <= 18f) result.crosses_east_door = true;
                }
                if (a.y <= 3.5f && b.y >= 3.5f && Mathf.Abs(b.y - a.y) > 0.001f)
                {
                    var fraction = (3.5f - a.y) / (b.y - a.y);
                    var x = Mathf.Lerp(a.x, b.x, fraction);
                    var z = Mathf.Lerp(a.z, b.z, fraction);
                    if (x >= 27.5f && x <= 29.5f && z >= 17f && z <= 25f)
                        result.ascends_stair = true;
                }
            }
            if (!result.crosses_east_door || !result.ascends_stair)
                throw new InvalidOperationException("direct interior path missed door or stair");
            result.status = "pass";
            Debug.Log("WorldBuilder first city interior navigation: " +
                result.direct_path_length_m + " m direct path via east door and stair");
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
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V2_INTERIOR_NAV_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v2-interior-nav-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }

    private static void WriteReopenResult(ReopenResult result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V2_INTERIOR_NAV_REOPEN_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v2-interior-nav-reopen-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
