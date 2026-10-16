using UnityEngine;

/// <summary>City overview shortcuts and optional manual collision walking.</summary>
public sealed class WorldBuilderCityExplorer : MonoBehaviour
{
    public float streetY=84,riverX=256,castleX=416;
    public float regionM;
    public Vector3 overviewPosition,overviewTarget,streetPosition,streetTarget,riverPosition,riverTarget,castlePosition,castleTarget,spawnPosition;
    CharacterController controller;
    bool walking;
    float fall;

    void Start()
    {
        controller=gameObject.AddComponent<CharacterController>();
        controller.height=1.8f;controller.radius=.28f;controller.center=new Vector3(0,-.8f,0);
        controller.skinWidth=.015f;controller.stepOffset=.3f;controller.enabled=false;
        Application.targetFrameRate=60;
    }
    void View(Vector3 position,Vector3 target)
    {
        walking=false;controller.enabled=false;transform.position=position;transform.LookAt(target);
    }
    void Update()
    {
        if(Input.GetKeyDown(KeyCode.Alpha1))View(regionM>0?overviewPosition:new Vector3(720,520,-240),regionM>0?overviewTarget:new Vector3(256,0,240));
        if(Input.GetKeyDown(KeyCode.Alpha2))View(regionM>0?streetPosition:new Vector3(72,4,streetY),regionM>0?streetTarget:new Vector3(185,4,streetY));
        if(Input.GetKeyDown(KeyCode.Alpha3))View(regionM>0?castlePosition:new Vector3(castleX+95,65,387),regionM>0?castleTarget:new Vector3(castleX,8,462));
        if(Input.GetKeyDown(KeyCode.Alpha4))View(regionM>0?riverPosition:new Vector3(riverX+45,24,streetY-55),regionM>0?riverTarget:new Vector3(riverX,2,streetY+30));
        if(Input.GetKeyDown(KeyCode.F))
        {
            walking=!walking;controller.enabled=false;fall=0;
            if(walking){transform.position=regionM>0?spawnPosition:new Vector3(72,2.8f,streetY);transform.eulerAngles=new Vector3(0,90,0);}
            controller.enabled=walking;
        }
        if(Input.GetMouseButton(1))
        {
            var angles=transform.eulerAngles;angles.x-=Input.GetAxis("Mouse Y")*2;angles.y+=Input.GetAxis("Mouse X")*2;
            transform.eulerAngles=angles;
        }
        float h=Input.GetAxisRaw("Horizontal"),v=Input.GetAxisRaw("Vertical");
        if(walking)
        {
            Vector3 forward=Vector3.ProjectOnPlane(transform.forward,Vector3.up).normalized;
            Vector3 right=Vector3.ProjectOnPlane(transform.right,Vector3.up).normalized;
            Vector3 move=(forward*v+right*h).normalized*(Input.GetKey(KeyCode.LeftShift)?7:3.5f);
            if(controller.isGrounded)fall=-2;else fall-=20*Time.deltaTime;
            move.y=fall;controller.Move(move*Time.deltaTime);
        }
        else
        {
            float up=(Input.GetKey(KeyCode.E)?1:0)-(Input.GetKey(KeyCode.Q)?1:0);
            transform.Translate(new Vector3(h,up,v)*(Input.GetKey(KeyCode.LeftShift)?100:30)*Time.deltaTime,Space.Self);
        }
    }
    void OnGUI()
    {
        GUI.Box(new Rect(12,12,570,49),(regionM>0?"768m Organic Valley":"512m Arcane City")+" | 1 Overview  2 Street  3 Castle  4 River\nWASD + right mouse | Q/E fly | Shift faster | F walk/fly");
    }
}
