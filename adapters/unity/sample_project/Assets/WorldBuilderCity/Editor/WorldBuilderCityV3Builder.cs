using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class WorldBuilderCityV3Builder
{
    [Serializable] private sealed class Piece
    {
        public string name;
        public string source_id;
        public string chunk_id;
    }
    [Serializable] private sealed class Chunk
    {
        public string id;
        public string path;
        public string glb_sha256;
        public int piece_count;
    }
    [Serializable] private sealed class Manifest
    {
        public string source_world_id;
        public string source_revision_id;
        public string adapter_version;
        public string unity_version;
        public Chunk[] chunks;
        public Piece[] pieces;
    }
    [Serializable] private sealed class Result
    {
        public string unity_version;
        public string source_world_id;
        public string source_revision_id;
        public string target_load = "failed";
        public string collision = "not_run";
        public string normals = "not_run";
        public string triangle_size = "not_run";
        public string bridge_orientation = "not_run";
        public int expected_chunks;
        public int loaded_chunks;
        public int expected_pieces;
        public int mapped_pieces;
        public int mesh_colliders;
        public float largest_triangle_edge_m;
        public string scene_path;
        public string error;
    }

    private const string Base = "Assets/WorldBuilderCity/v3/";

    [MenuItem("World Builder/Build Chunked City v3")]
    public static void Build()
    {
        var result = new Result { unity_version = Application.unityVersion,
            scene_path = Base + "CityChunks.unity" };
        try
        {
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var manifest = JsonUtility.FromJson<Manifest>(File.ReadAllText(
                Path.Combine(Application.dataPath, "WorldBuilderCity", "v3", "manifest.json")));
            if (manifest == null || manifest.adapter_version != "0.1.0-city.3" ||
                manifest.unity_version != Application.unityVersion ||
                manifest.chunks == null || manifest.pieces == null)
                throw new InvalidOperationException("city v3 manifest or Unity profile mismatch");
            result.source_world_id = manifest.source_world_id;
            result.source_revision_id = manifest.source_revision_id;
            result.expected_chunks = manifest.chunks.Length;
            result.expected_pieces = manifest.pieces.Length;
            if (result.expected_chunks == 0 || result.expected_pieces == 0)
                throw new InvalidOperationException("empty city v3 manifest");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var world = new GameObject(manifest.source_world_id);
            var found = new HashSet<string>();
            var bridgeBounds = new Bounds();
            var bridgeFound = false;
            foreach (var chunk in manifest.chunks)
            {
                var chunkPath = Path.Combine(Application.dataPath, "WorldBuilderCity", "v3",
                    chunk.path.Replace('/', Path.DirectorySeparatorChar));
                using (var sha = SHA256.Create())
                {
                    var actual = "sha256:" + BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(chunkPath)))
                        .Replace("-", "").ToLowerInvariant();
                    if (actual != chunk.glb_sha256)
                        throw new InvalidOperationException("chunk SHA-256 mismatch: " + chunk.path);
                }
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(Base + chunk.path);
                if (prefab == null) throw new InvalidOperationException("missing chunk GLB: " + chunk.path);
                var root = UnityEngine.Object.Instantiate(prefab, world.transform);
                root.name = chunk.id;
                result.loaded_chunks++;
                var count = 0;
                foreach (var piece in manifest.pieces)
                {
                    if (piece.chunk_id != chunk.id) continue;
                    if (!found.Add(piece.name)) throw new InvalidOperationException("duplicate piece: " + piece.name);
                    var part = Find(root.transform, piece.name);
                    if (part == null) throw new InvalidOperationException("missing piece: " + piece.name);
                    part.gameObject.AddComponent<WorldBuilderSourceId>().sourceId = piece.source_id;
                    var filters = part.GetComponentsInChildren<MeshFilter>(true);
                    if (filters.Length != 1 || filters[0].sharedMesh == null)
                        throw new InvalidOperationException("expected one mesh: " + piece.name);
                    var filter = filters[0];
                    var mesh = filter.sharedMesh;
                    filter.gameObject.AddComponent<MeshCollider>().sharedMesh = mesh;
                    if (mesh.normals.Length != mesh.vertexCount)
                        throw new InvalidOperationException("missing vertex normals: " + piece.name);
                    var vertices = mesh.vertices;
                    var triangles = mesh.triangles;
                    for (var i = 0; i < triangles.Length; i += 3)
                    {
                        var localA = vertices[triangles[i]];
                        var localB = vertices[triangles[i + 1]];
                        var localC = vertices[triangles[i + 2]];
                        if (Vector3.Dot(Vector3.Cross(localB - localA, localC - localA),
                            mesh.normals[triangles[i]]) <= 0f)
                            throw new InvalidOperationException("normal/winding mismatch: " + piece.name);
                        var a = filter.transform.TransformPoint(localA);
                        var b = filter.transform.TransformPoint(localB);
                        var c = filter.transform.TransformPoint(localC);
                        result.largest_triangle_edge_m = Mathf.Max(result.largest_triangle_edge_m,
                            Vector3.Distance(a, b), Vector3.Distance(b, c), Vector3.Distance(c, a));
                    }
                    if (piece.source_id == "bridge_main")
                    {
                        var bounds = filter.GetComponent<Renderer>().bounds;
                        if (bridgeFound) bridgeBounds.Encapsulate(bounds);
                        else { bridgeBounds = bounds; bridgeFound = true; }
                    }
                    result.mapped_pieces++;
                    result.mesh_colliders++;
                    count++;
                }
                if (count != chunk.piece_count)
                    throw new InvalidOperationException("chunk piece count mismatch: " + chunk.id);
            }
            if (found.Count != result.expected_pieces)
                throw new InvalidOperationException("not all manifest pieces were mapped");
            result.collision = result.mesh_colliders == result.expected_pieces ? "pass" : "failed";
            result.normals = "pass";
            result.triangle_size = result.largest_triangle_edge_m < 182f ? "pass" : "failed";
            if (result.triangle_size != "pass") throw new InvalidOperationException("oversized triangle");
            result.bridge_orientation = bridgeFound && Near(bridgeBounds.min.x, 252f) &&
                Near(bridgeBounds.max.x, 260f) && Near(bridgeBounds.min.y, 1.6f) &&
                Near(bridgeBounds.max.y, 2f) && Near(bridgeBounds.min.z, 268f) &&
                Near(bridgeBounds.max.z, 274f) ? "pass" : "failed";
            if (result.bridge_orientation != "pass")
                throw new InvalidOperationException("bridge orientation or bounds changed: " + bridgeBounds);

            var light = new GameObject("Sun").AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.4f;
            light.transform.rotation = Quaternion.Euler(40f, -30f, 0f);
            var camera = new GameObject("Overview Camera").AddComponent<Camera>();
            camera.tag = "MainCamera";
            camera.transform.position = new Vector3(24f, 17f, 3f);
            camera.transform.LookAt(new Vector3(24f, 5f, 22f));
            EditorSceneManager.SaveScene(scene, result.scene_path);
            AssetDatabase.SaveAssets();
            result.target_load = "pass";
            Debug.Log("WorldBuilder city v3 imported: " + result.loaded_chunks + " chunks, " +
                      result.mapped_pieces + " pieces, max triangle edge " + result.largest_triangle_edge_m);
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

    private static bool Near(float actual, float expected) => Math.Abs(actual - expected) <= 0.02f;

    private static Transform Find(Transform root, string name)
    {
        if (root.name == name) return root;
        foreach (Transform child in root)
        {
            var match = Find(child, name);
            if (match != null) return match;
        }
        return null;
    }

    private static void WriteResult(Result result)
    {
        var path = Environment.GetEnvironmentVariable("WORLD_BUILDER_UNITY_CITY_V3_VALIDATION");
        if (string.IsNullOrEmpty(path))
            path = Path.GetFullPath(Path.Combine(Application.dataPath,
                "../../../../artifacts/unity-city/v3-target-validation.json"));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path, JsonUtility.ToJson(result, true));
    }
}
