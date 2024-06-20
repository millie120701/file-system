from time import time, sleep
from datetime import datetime
from filesystemapp import mycursor, connection

class FileSystemExceptions(Exception):
        def __init__(self, message=""):
            super().__init__(message)

class FilePathDoesNotExist(FileSystemExceptions):
    pass

class FileSystemObject:
    """
    shared code between files and folders
    """
    def __init__(self,name):
        self.name = name
        self.last_modified = None
        self.parent_folder = None

    def update_last_modified(self, modified_time=None):
            """
            set the last modified time (memory + database) on THIS object
            if a parent exists, call update_last_modified on the parent
            """
            if modified_time is None:
                modified_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self.last_modified = modified_time
            if self.parent_folder is not None:
                sql_update = "UPDATE Folders SET last_modified = %s WHERE filepath = %s" #some folders may share the same name
                val = (modified_time, self.get_full_path())
                mycursor.execute(sql_update, val)
                connection.commit()
                self.parent_folder.update_last_modified(modified_time)


    def get_full_path(self):
        if self.parent_folder is None:
            return "/" + self.name
        else:
            parent_path = self.parent_folder.get_full_path()
            return parent_path + "/" + self.name
        
    def get_size(self):
        pass # ABSTRACT METHOD - overridden on child classes

    def rename(self, new_name):
        """
        changes name of file or folder, updates the db
        file change: 
        - file itself only: name, path
        - parent folders and file itself: last modified
        folder change: 
        - folder itself only: name
        - parent folders and folder itself: last modified
        - daughter folders/files and folder itself -- path change
        """
        #assign old name, old path and new name
        old_name = self.name 
        old_path = self.get_full_path()
        self.name = new_name
        new_path = self.get_full_path() # -> performance gain opportunity: instead of re-calculating the whole string, modify old_path (with .split())

        #update last modified of parent folders and file/folder itself, sql handled by update_last_modified()
        #irrespective of type of the change (whether folder or file)

        last_modified = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.last_modified = last_modified
        if self.parent_folder is not None:
            self.parent_folder.update_last_modified(last_modified)
        
        if type(self) == File:
            #update file with new filepath and name using old filepath, last modified already sorted
            sql_file_change_update_file =  "UPDATE Files SET name = %s, filepath = %s WHERE filepath = %s"
            val_file_change_update_file = (self.name, new_path, old_path) #new name, new path, old path
            mycursor.execute(sql_file_change_update_file, val_file_change_update_file)
            connection.commit()

        else: #type is a folder
            #change folder name of folder itself
            sql_folder_change_update_folder = "UPDATE Folders SET name = %s WHERE filepath = %s"
            val_folder_change_update_folder = (self.name, old_path)
            mycursor.execute(sql_folder_change_update_folder, val_folder_change_update_folder)
            connection.commit()
            #change path of daughter folders and folder itself
            sql_folder_change_update_path_of_folders = "UPDATE Folders SET filepath = REPLACE(filepath, %s, %s) WHERE filepath LIKE %s"
            val_folder_change_update_path_of_folders = (old_path, new_path, old_path + '%')
            mycursor.execute(sql_folder_change_update_path_of_folders, val_folder_change_update_path_of_folders)
            connection.commit()
            #change file path of daughter files
            sql_folder_change_update_path_of_files = "UPDATE Files SET filepath = REPLACE(filepath, %s, %s) WHERE filepath LIKE %s"
            val_folder_change_update_path_of_files = (old_path, new_path, old_path + '%')
            mycursor.execute(sql_folder_change_update_path_of_files, val_folder_change_update_path_of_files)
            connection.commit()



class Folder(FileSystemObject):
    """
    A container which contains a collection of files and folders.
    """
    def __init__(self, name):
        super().__init__(name)
        self.content = [] # list of File and Folder objects

    def __repr__(self):
        return self.name

    def listdir(self):
        # prints the content of the current folder (not recursing subfolders)
        for item in self.content:
            print(item)

    def add_file(self, name):
        new_file = File(name)
        new_file.parent_folder = self
        self.content.append(new_file)
        new_file.update_last_modified()
        sql = "INSERT INTO Files (name, last_modified, filepath) VALUES (%s, %s, %s)"
        val = (new_file.name, new_file.last_modified, new_file.get_full_path()) 
        mycursor.execute(sql, val)
        connection.commit()

        return new_file

    def add_folder(self, name):
        new_folder = Folder(name)
        new_folder.parent_folder = self
        self.content.append(new_folder)
        new_folder.update_last_modified()
        #insert folder into database
        sql_insert = "INSERT INTO Folders (name, last_modified, filepath) VALUES (%s, %s, %s)"
        val = (new_folder.name, new_folder.last_modified, new_folder.get_full_path())
        mycursor.execute(sql_insert, val)
        connection.commit()
     
        return new_folder

    def get_size(self):
        total_size = 0
        for item in self.content:
            total_size += item.get_size() # iterate across files and folders and call their common get_size method, which returns an int
        return total_size

    def modify_file(self, filepath, new_content):   
        current_path = filepath.split("/") 
        if "/" in filepath: 
            new_path = "/".join(current_path[1:]) 
            target_folder = current_path[0]  
            for folder in self.content:
                if type(folder) == Folder and folder.name == target_folder:
                    folder.modify_file(new_path, new_content)
        else:
            for file in self.content:
                if type(file) == File and file.name == current_path[0]:
                    file.modify(new_content)
    
    def return_object(self, filepath):#e.g. stuff.return_object("more_stuff/things/notes.txt")
        current_path = filepath.split("/")
        if "/" in filepath:
            new_path = "/".join(current_path[1:])  #things/notes.txt
            target_folder = current_path[0]  
            for folder in self.content:
                if type(folder) == Folder and folder.name == target_folder:
                   return folder.return_object(new_path)
        else:
            for item in self.content:
                if item.name == current_path[0]:
                    return item
                
    def update_folder_size(self):
        sql_update = "UPDATE Folders SET size = %s WHERE filepath = %s" #some folders may share the same name
        val = (self.get_size(), self.get_full_path())
        mycursor.execute(sql_update, val)
        connection.commit()
        if self.parent_folder is not None:
            self.parent_folder.update_folder_size()
    


class File(FileSystemObject):
    """
    A piece of data (string) and associated metadata.
    """
    def __init__(self, name):
        super().__init__(name)
        self.content = ""
        self.file_size = 0

    def __repr__(self):
        return self.name

    def modify(self, content):
        #replaces old content with new WHAT IF FILE HAS SAME NAME??
        self.content = content
        last_modified = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.last_modified = last_modified
        sql_update = "UPDATE Files SET content = %s, size = %s, last_modified = %s WHERE filepath = %s"
        val = (self.content, self.get_size(), last_modified,self.get_full_path())
        mycursor.execute(sql_update, val)
        connection.commit()
        #get parent folders and update their time
        if self.parent_folder != None:
            self.parent_folder.update_last_modified(last_modified)
            self.parent_folder.update_folder_size()
      


    def get_size(self):
        #length of content in the file
        return len(self.content)

class FileSystem:
    def __init__(self):
        self.root_folder = Folder("root")

    def modify_file(self, filepath, new_content):
        new_path = "/".join(filepath.split("/")[1:])
        self.root_folder.modify_file(new_path, new_content)

    def get_total_size(self):
         return self.root_folder.get_size()

    def get_root(self):
        return self.root_folder
    
    def return_object(self, filepath):
            new_path = "/".join(filepath.split("/")[1:])
            return self.root_folder.return_object(new_path)
      



if __name__ == "__main__":
        """
    mfs = FileSystem()
    root = mfs.get_root()
    root_file = root.add_file("root_file")
    sleep(2)
    stuff = root.add_folder("stuff")
    sleep(2)
    notes = stuff.add_file("notes.txt")
    sleep(2)
    fun = root.add_folder("new-FOLDER")
    sleep(2)
    nnn = stuff.add_folder("new")
    sleep(2)
    f = nnn.add_file("mameeee")
    f.modify('Hey')

    print(f.last_modified)
    print(nnn.last_modified)
    print(root.last_modified)
    print(stuff.last_modified)
    print(fun.last_modified)

    hello = stuff.add_file("hello.txt")
    more_stuff = stuff.add_folder("more_stuff")
    notes = more_stuff.add_file("notes.txt")
    root.add_file("hello.mp3")
    more_stuff.add_file("james-is-a-funion.txt")

    notes.modify("hello") 
    hello.modify("hi")
    print(stuff.get_size())
    print(more_stuff.get_size()) 

    print(mfs.get_total_size())

    root.modify_file("stuff/more_stuff/notes.txt", "yokkkk")
    print(notes.content)
   
    jfs = FileSystem()
    root = jfs.get_root()
    root.add_folder("test1")
    root.add_file("blah").modify("lkjhgfds")
    t2 = root.add_folder("test2")
    t3 = root.add_folder("test3")
    t3.add_file("blah")
    root.add_folder("test4")
    root.add_file("hello.mp4")
    root.add_file("itsme")
    root.add_file("funion")
    t2.add_file("test.txt")
    t2.add_file("anothertest")
    t2.add_folder("anothertest")
    t2.add_folder("anothertest2")
    st = t2.add_folder("stufftest")
    notes = st.add_file("mynotes")
    notes.modify("this is the content")
    more_notes = t2.add_file("morenotes.txt")
    more_notes.modify("millie is funion")
    print(t3.last_modified)
    print(t2.last_modified)
    


    #print(more_notes.get_full_path())

    jfs.modify_file("root/test2/morenotes.txt", "new stuff")
    #print(more_notes.content)
    #print(t2.last_modified)
    #print(t3.last_modified)
    
    n = jfs.return_object("root/test2/morenotes.txt")
    print(n.content)

    """






